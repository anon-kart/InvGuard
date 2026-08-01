"""
template_patches.py — Deterministic vulnerability patches
==========================================================
Applies known fix patterns for each vulnerability class.
No LLM — pure string transformation. Called as a fallback
when FixMaker's LLM-generated patches fail the gate.

Each function takes the original contract source + target function name
and returns the patched source, or None if the pattern isn't recognized.
"""
import re


def patch_reentrancy(src: str, target_fn: str) -> str:
    """
    Insert a reentrancy mutex (nonReentrant modifier).

    Strategy:
    1. Add `bool private _locked;` state variable
    2. Add `modifier nonReentrant()` 
    3. Add `nonReentrant` to the target function's modifiers
    """
    if not src or not target_fn:
        return None

    # Don't double-patch
    if "nonReentrant" in src or "_locked" in src:
        return None

    # Find the first contract declaration
    cm = re.search(r"(\bcontract\s+\w+[^{]*\{)", src)
    if not cm:
        return None

    # Insert state variable and modifier after the opening brace
    mutex_code = """
    bool private _locked;
    modifier nonReentrant() {
        require(!_locked);
        _locked = true;
        _;
        _locked = false;
    }
"""
    patched = src[:cm.end()] + mutex_code + src[cm.end():]

    # Add nonReentrant to the target function
    # Match: function targetFn(...) [public|external] [payable] [returns(...)] {
    fn_pattern = re.compile(
        r"(function\s+" + re.escape(target_fn) + r"\s*\([^)]*\)"
        r"[^{]*?)"  # everything before the opening brace
        r"(\{)",
        re.DOTALL
    )
    m = fn_pattern.search(patched)
    if m:
        fn_header = m.group(1)
        # Insert nonReentrant before the opening brace
        if "nonReentrant" not in fn_header:
            patched = patched[:m.start(2)] + "nonReentrant " + patched[m.start(2):]

    return patched


def patch_access_control(src: str, target_fn: str) -> str:
    """
    Add access control to an unprotected function.

    Strategy:
    1. Detect the contract's existing owner pattern
    2. Add the appropriate require check to the target function
    """
    if not src or not target_fn:
        return None

    # Detect owner patterns (most common to least)
    owner_checks = []

    # Pattern: modifier onlyOwner exists but not applied to target
    if re.search(r"modifier\s+onlyOwner", src):
        # Add onlyOwner modifier to the function
        fn_pattern = re.compile(
            r"(function\s+" + re.escape(target_fn) + r"\s*\([^)]*\)"
            r"[^{]*?)"
            r"(\{)",
            re.DOTALL
        )
        m = fn_pattern.search(src)
        if m and "onlyOwner" not in m.group(1):
            return src[:m.start(2)] + "onlyOwner " + src[m.start(2):]

    # Pattern: `address public owner` or `address public root`
    owner_var = None
    for var in ["owner", "root", "creator", "_owner", "admin"]:
        if re.search(r"address\s+(?:public\s+)?" + re.escape(var) + r"\b", src):
            owner_var = var
            break

    # Pattern: `mapping (address => address) public owners`
    if not owner_var and re.search(r"mapping\s*\(\s*address\s*=>\s*address\s*\)\s*(?:public\s+)?owners", src):
        owner_checks.append("require(owners[msg.sender] != address(0));")

    if owner_var:
        owner_checks.append(f"require(msg.sender == {owner_var});")

    if not owner_checks:
        # Last resort: add a generic owner check with the constructor sender
        # Add an owner variable
        cm = re.search(r"(\bcontract\s+\w+[^{]*\{)", src)
        if cm:
            src = src[:cm.end()] + "\n    address private _patchOwner;\n" + src[cm.end():]
            # Set in constructor
            ctor = re.search(r"(constructor\s*\([^)]*\)[^{]*\{)", src)
            if ctor:
                src = src[:ctor.end()] + "\n        _patchOwner = msg.sender;\n" + src[ctor.end():]
            # Also try function-style constructor for pre-0.4.22
            else:
                contract_name = re.search(r"contract\s+(\w+)", src)
                if contract_name:
                    fname = contract_name.group(1)
                    old_ctor = re.search(
                        r"(function\s+" + re.escape(fname) + r"\s*\([^)]*\)[^{]*\{)", src
                    )
                    if old_ctor:
                        src = src[:old_ctor.end()] + "\n        _patchOwner = msg.sender;\n" + src[old_ctor.end():]
            owner_checks.append("require(msg.sender == _patchOwner);")

    if not owner_checks:
        return None

    # Insert the check at the start of the target function body
    fn_pattern = re.compile(
        r"(function\s+" + re.escape(target_fn) + r"\s*\([^)]*\)[^{]*\{)",
        re.DOTALL
    )
    m = fn_pattern.search(src)
    if not m:
        return None

    check = "\n        " + owner_checks[0] + "\n"

    # Don't add if already has a require(msg.sender check
    fn_body_start = m.end()
    fn_body_snippet = src[fn_body_start:fn_body_start + 200]
    if "require(msg.sender" in fn_body_snippet or "require(owners[msg.sender" in fn_body_snippet:
        return None

    return src[:m.end()] + check + src[m.end():]


def patch_unchecked_call(src: str, target_fn: str) -> str:
    """
    Wrap unchecked .send() and .transfer() in require().

    Strategy: find .send(x) not inside require() and wrap it.
    """
    if not src or not target_fn:
        return None

    patched = src

    # Pattern: addr.send(x) not wrapped in require
    # Match: var.send(expr) that's NOT inside require(...)
    # Simple heuristic: if the line has .send( but not require(
    lines = patched.split("\n")
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if ".send(" in stripped and "require(" not in stripped:
            # Replace: addr.send(x) → require(addr.send(x))
            # Find the statement
            m = re.search(r"(\w[\w.]*\.send\([^)]+\))", stripped)
            if m:
                old = m.group(1)
                new = f"require({old})"
                lines[i] = line.replace(old, new)
                changed = True

    if not changed:
        # Try .call.value pattern without return check
        for i, line in enumerate(lines):
            stripped = line.strip()
            if ".call.value(" in stripped and "require(" not in stripped and "bool" not in stripped:
                # Wrap in require
                m = re.search(r"(\w[\w.]*\.call\.value\([^)]*\)\([^)]*\))", stripped)
                if m:
                    old = m.group(1)
                    new = f"require({old})"
                    lines[i] = line.replace(old, new)
                    changed = True

    if changed:
        return "\n".join(lines)
    return None


def patch_integer_overflow(src: str, target_fn: str) -> str:
    """
    Add overflow checks before arithmetic operations.

    Strategy: find + and * operations on uint and add require checks,
    or add SafeMath-style wrappers.
    """
    if not src or not target_fn:
        return None

    # Find the target function body
    fn_pattern = re.compile(
        r"(function\s+" + re.escape(target_fn) + r"\s*\([^)]*\)[^{]*\{)",
        re.DOTALL
    )
    m = fn_pattern.search(src)
    if not m:
        return None

    fn_start = m.end()

    # Find matching closing brace
    depth = 1
    pos = fn_start
    while pos < len(src) and depth > 0:
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
        pos += 1
    fn_body = src[fn_start:pos - 1]

    # Find assignments with + or * that could overflow
    # Pattern: var = expr + expr or var += expr
    overflow_ops = re.findall(r"(\w+)\s*(?:\+\=|=\s*\w+\s*\+)", fn_body)

    if not overflow_ops:
        return None

    # Add require checks before the function body
    checks = []
    for var in set(overflow_ops):
        # Add a generic overflow check
        pass  # Overflow checks are contract-specific, hard to template

    # Simpler approach: add `require(result >= a)` after additions
    patched = src
    # Replace += with checked addition
    new_body = re.sub(
        r"(\w+)\s*\+=\s*(\w+)\s*;",
        r"\1 += \2; require(\1 >= \2);",
        fn_body
    )
    if new_body != fn_body:
        patched = src[:fn_start] + new_body + src[pos - 1:]
        return patched

    return None


def apply_template_patch(src: str, vuln_class: str, target_fn: str) -> str:
    """
    Main entry point. Returns patched source or None.
    """
    patchers = {
        "reentrancy": patch_reentrancy,
        "access_control": patch_access_control,
        "unchecked_call": patch_unchecked_call,
        "unchecked_return": patch_unchecked_call,
        "integer_overflow": patch_integer_overflow,
    }

    patcher = patchers.get(vuln_class)
    if not patcher:
        return None

    return patcher(src, target_fn)
