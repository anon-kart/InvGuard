# flow_2_files/benign_executor.py
import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


# ---------------------------
# Small helpers
# ---------------------------

def _head(s: str, max_lines: int = 120) -> str:
    lines = (s or "").splitlines()
    return "\n".join(lines[:max_lines])


def _detect_first_contract_name(sol_src: str) -> Optional[str]:
    m = re.search(r"\bcontract\s+([A-Za-z_][A-Za-z0-9_]*)\b", sol_src)
    return m.group(1) if m else None


def _wrap_target_alias_if_needed(target_src: str) -> str:
    # If user already has a contract named Target, keep as-is.
    if re.search(r"\bcontract\s+Target\b", target_src):
        return target_src

    name = _detect_first_contract_name(target_src)
    if not name:
        return target_src

    alias = f"""

// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `{name}` has a no-arg constructor (or implicit constructor).
contract Target is {name} {{
    constructor() {name}() {{}}
}}
"""
    return target_src.rstrip() + "\n" + alias


def _extract_named_uint(stdout: str, name: str) -> Optional[int]:
    """
    Extracts forge log format:
      <name>: <digits>
    Works with forge-std log_named_uint.
    """
    if not stdout:
        return None
    m = re.search(rf"\b{re.escape(name)}\s*:\s*(\d+)\b", stdout)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _parse_public_mutating_functions(sol_src: str, limit: int = 12) -> List[Tuple[str, List[str], bool]]:
    """
    Very lightweight signature extractor.
    Returns list of (fn_name, arg_types, is_payable) for public/external, non-view/pure.
    Supported arg types: uint256,address,bool
    """
    out: List[Tuple[str, List[str], bool]] = []

    pat = re.compile(
        r"function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:public|external)\b([^;{]*)",
        re.MULTILINE,
    )

    for m in pat.finditer(sol_src or ""):
        fn = m.group(1)
        args_blob = (m.group(2) or "").strip()
        tail = (m.group(3) or "")

        # Skip view/pure
        if re.search(r"\bview\b|\bpure\b", tail):
            continue

        is_payable = bool(re.search(r"\bpayable\b", tail))

        arg_types: List[str] = []
        if args_blob:
            parts = [p.strip() for p in args_blob.split(",") if p.strip()]
            for p in parts:
                t = p.split()[0].strip()
                if t in ("uint", "uint256"):
                    arg_types.append("uint256")
                elif t == "address":
                    arg_types.append("address")
                elif t == "bool":
                    arg_types.append("bool")
                else:
                    # unsupported -> skip this function
                    arg_types = []
                    break

        # If unsupported arg encountered, skip
        if arg_types is None:
            continue

        out.append((fn, arg_types, is_payable))
        if len(out) >= limit:
            break

    return out


def _make_arg_expr(t: str, idx: int) -> str:
    # Deterministic benign args
    if t == "uint256":
        return "uint256(1)"
    if t == "address":
        return "address(this)"
    if t == "bool":
        return "true"
    raise ValueError(f"unsupported benign arg type: {t}")


def _make_sig(fn: str, arg_types: List[str]) -> str:
    return f"{fn}({','.join(arg_types)})"


def _write_foundry_project(project_dir: Path, target_contract_src: str) -> None:
    src_dir = project_dir / "src"
    test_dir = project_dir / "test"
    src_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "foundry.toml").write_text(
        "\n".join(
            [
                "[profile.default]",
                'src = "src"',
                'out = "out"',
                'libs = ["lib"]',
                'remappings = ["forge-std/=lib/forge-std/src/"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    (src_dir / "Target.sol").write_text(_wrap_target_alias_if_needed(target_contract_src), encoding="utf-8")

    # Vendor minimal forge-std locally (no network, no git required).
    # This matches what exploit_executor.py already does correctly.
    forge_std_src = project_dir / "lib" / "forge-std" / "src"
    forge_std_src.mkdir(parents=True, exist_ok=True)

    _FORGE_STD_MINIMAL = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface Vm {
    function deal(address who, uint256 newBalance) external;
    function prank(address sender) external;
    function startPrank(address sender) external;
    function stopPrank() external;
    function snapshot() external returns (uint256);
    function revertTo(uint256 id) external returns (bool);
    function expectRevert() external;
    function expectRevert(bytes calldata revertData) external;
}

contract Test {
    Vm public constant vm =
        Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    event log_named_uint(string key, uint256 val);
    event log_named_bytes(string key, bytes val);
    event log_named_int(string key, int256 val);
    event log_named_address(string key, address val);
    event log_named_string(string key, string val);
}
"""
    (forge_std_src / "Test.sol").write_text(_FORGE_STD_MINIMAL, encoding="utf-8")


def _should_seed_eth(calls: List[Tuple[str, List[str], bool]]) -> bool:
    """
    Avoid ForceSend masking regressions:
      - seed only if any payable fn exists OR fn name hints at needing contract ETH.
    """
    suspicious = re.compile(r"(withdraw|claim|transfer|redeem|swap|borrow|repay|mint|burn|deposit)", re.IGNORECASE)
    for fn, _arg_types, is_payable in calls:
        if is_payable or suspicious.search(fn):
            return True
    return False


def _write_benign_test(project_dir: Path, calls: List[Tuple[str, List[str], bool]]) -> None:
    """
    Writes a single Foundry test that:
      - deploys Target
      - defines user address
      - optionally seeds target with small ETH only if needed
      - for each call (snapshot-isolated):
          * run as owner-ish (this test contract)
          * run as user (vm.startPrank/user)
          * logs:
              - c{i}_owner, c{i}_user
              - target balance before/after per sender
              - sender balance before/after per sender
      - logs global target balance before/after for coarse sanity
    """
    test_dir = project_dir / "test"
    seed_needed = _should_seed_eth(calls)

    call_blocks = []
    for i, (fn, arg_types, is_payable) in enumerate(calls):
        sig = _make_sig(fn, arg_types)
        args = ", ".join(_make_arg_expr(t, i) for t in arg_types)
        calldata_expr = f'abi.encodeWithSignature("{sig}"' + (f", {args}" if args else "") + ")"
        value_expr = "0.01 ether" if is_payable else "0"

        call_blocks.append(
            f"""
        {{
            uint256 snap = vm.snapshot();

            // -----------------
            // OWNER-ish call
            // -----------------
            uint256 t0_owner = address(target).balance;
            uint256 s0_owner = address(this).balance;

            (bool ok_owner, ) = address(target).call{{value: {value_expr}}}({calldata_expr});

            uint256 t1_owner = address(target).balance;
            uint256 s1_owner = address(this).balance;

            emit log_named_uint("c{i}_owner", ok_owner ? 1 : 0);
            emit log_named_uint("t{i}_owner_before", t0_owner);
            emit log_named_uint("t{i}_owner_after",  t1_owner);
            emit log_named_uint("s{i}_owner_before", s0_owner);
            emit log_named_uint("s{i}_owner_after",  s1_owner);

            // -----------------
            // USER call
            // -----------------
            vm.startPrank(user);

            uint256 t0_user = address(target).balance;
            uint256 s0_user = user.balance;

            (bool ok_user, ) = address(target).call{{value: {value_expr}}}({calldata_expr});

            uint256 t1_user = address(target).balance;
            uint256 s1_user = user.balance;

            vm.stopPrank();

            emit log_named_uint("c{i}_user", ok_user ? 1 : 0);
            emit log_named_uint("t{i}_user_before", t0_user);
            emit log_named_uint("t{i}_user_after",  t1_user);
            emit log_named_uint("s{i}_user_before", s0_user);
            emit log_named_uint("s{i}_user_after",  s1_user);

            vm.revertTo(snap);
        }}
"""
        )

    seed_block = ""
    if seed_needed:
        seed_block = """
        // seed target with a SMALL amount of ETH only if needed
        new ForceSend{value: 0.1 ether}().go(payable(address(target)));
"""

    test_code = f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/Target.sol";

contract ForceSend {{
    constructor() payable {{}}
    function go(address payable to) external {{
        selfdestruct(to);
    }}
}}

contract BenignBehaviorTest is Test {{
    function test_benign_calls() public {{
        Target target = new Target();
        address user = address(0xB0B);

        vm.deal(address(this), 100 ether);
        vm.deal(user, 100 ether);

        emit log_named_uint("bal_before", address(target).balance);
{seed_block}
{''.join(call_blocks)}
        emit log_named_uint("bal_after", address(target).balance);
    }}
}}
'''
    (test_dir / "BenignBehavior.t.sol").write_text(test_code, encoding="utf-8")


def _find_forge() -> str:
    """Find forge binary: check shutil.which, then common locations."""
    import shutil as _shutil
    f = _shutil.which("forge")
    if f:
        return f
    for p in [
        "/home/kartik/.foundry/bin/forge",
        "/root/.foundry/bin/forge",
        "/usr/local/bin/forge",
        str(Path.home() / ".foundry" / "bin" / "forge"),
    ]:
        if Path(p).exists():
            return p
    return "forge"  # fallback


def _run_benign(project_dir: Path) -> Tuple[bool, int, str, str]:
    forge = _find_forge()
    proc = subprocess.run(
        [forge, "test", "-vv"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return (proc.returncode == 0, proc.returncode, proc.stdout or "", proc.stderr or "")


def run_benign_suite_once(
    base_out_dir: str,
    contract_src: str,
    tag: str,
    calls: Optional[List[Tuple[str, List[str], bool]]] = None,
) -> Dict[str, Any]:
    out_root = Path(base_out_dir) / "patch_validation" / "benign_executor" / tag
    if out_root.exists():
        shutil.rmtree(out_root, ignore_errors=True)
    out_root.mkdir(parents=True, exist_ok=True)

    if calls is None:
        calls = _parse_public_mutating_functions(contract_src, limit=12)

    if not calls:
        return {
            "ok": True,
            "calls": [],
            "results": [],
            "global_balance": {"before": 0, "after": 0, "delta": 0},
            "project_dir": str(out_root),
            "forge_returncode": 0,
            "stdout_head": "",
            "stderr_head": "",
            "error": None,
        }

    _write_foundry_project(out_root, contract_src)
    _write_benign_test(out_root, calls)

    ok, rc, stdout, stderr = _run_benign(out_root)

    def get(name: str) -> int:
        v = _extract_named_uint(stdout, name)
        return 0 if v is None else int(v)

    results: List[Dict[str, Any]] = []
    for i in range(len(calls)):
        results.append({
            "owner": {
                "ok": get(f"c{i}_owner"),
                "t_before": get(f"t{i}_owner_before"),
                "t_after":  get(f"t{i}_owner_after"),
                "s_before": get(f"s{i}_owner_before"),
                "s_after":  get(f"s{i}_owner_after"),
            },
            "user": {
                "ok": get(f"c{i}_user"),
                "t_before": get(f"t{i}_user_before"),
                "t_after":  get(f"t{i}_user_after"),
                "s_before": get(f"s{i}_user_before"),
                "s_after":  get(f"s{i}_user_after"),
            },
        })

    bal_before = get("bal_before")
    bal_after  = get("bal_after")
    global_delta = int(bal_after) - int(bal_before)

    return {
        "ok": ok,
        "calls": [{"fn": c[0], "arg_types": c[1], "payable": c[2]} for c in calls],
        "results": results,
        "global_balance": {"before": bal_before, "after": bal_after, "delta": global_delta},
        "project_dir": str(out_root),
        "forge_returncode": rc,
        "stdout_head": _head(stdout),
        "stderr_head": _head(stderr),
        "error": None if ok else "forge test failed",
    }


def run_benign_suite_differential(
    base_out_dir: str,
    original_contract_src: str,
    patched_contract_src: str,
) -> Dict[str, Any]:
    # Deterministic: generate call list ONCE from original only
    calls = _parse_public_mutating_functions(original_contract_src, limit=12)

    orig = run_benign_suite_once(base_out_dir, original_contract_src, tag="original", calls=calls)
    pat  = run_benign_suite_once(base_out_dir, patched_contract_src,   tag="patched",  calls=calls)

    failed_calls: List[Dict[str, Any]] = []
    ok = True

    # If original benign suite fails, we cannot trust differential semantics
    if not orig.get("ok", False):
        return {
            "ok": False,
            "reason": "benign_original_failed",
            "original": orig,
            "patched": pat,
            "failed_calls": [{"reason": "original_suite_failed"}],
        }

    # If patched suite fails, treat as regression
    if not pat.get("ok", False):
        ok = False
        failed_calls.append({"reason": "patched_suite_failed"})

    # Per-call, per-sender semantics
    for i, call in enumerate(orig.get("calls", [])):
        o = orig["results"][i] if i < len(orig["results"]) else {}
        p = pat["results"][i]  if i < len(pat["results"])  else {}

        for who in ("owner", "user"):
            o_w = (o.get(who) or {})
            p_w = (p.get(who) or {})

            o_ok = int(o_w.get("ok", 0))
            p_ok = int(p_w.get("ok", 0))

            # Rule 1: if original succeeded, patched must succeed
            if o_ok == 1 and p_ok != 1:
                ok = False
                failed_calls.append({
                    "index": i,
                    "sender": who,
                    "reason": "call_reverted_on_patch",
                    "call": call,
                    "original_ok": o_ok,
                    "patched_ok": p_ok,
                })
                continue

            # Only enforce semantic equality when original succeeded
            if o_ok != 1:
                continue

            # Rule 2: target balance delta must match
            o_t_delta = int(o_w.get("t_after", 0)) - int(o_w.get("t_before", 0))
            p_t_delta = int(p_w.get("t_after", 0)) - int(p_w.get("t_before", 0))
            if o_t_delta != p_t_delta:
                ok = False
                failed_calls.append({
                    "index": i,
                    "sender": who,
                    "reason": "target_balance_delta_mismatch",
                    "call": call,
                    "original_delta": o_t_delta,
                    "patched_delta": p_t_delta,
                    "original": {"t_before": o_w.get("t_before"), "t_after": o_w.get("t_after")},
                    "patched":  {"t_before": p_w.get("t_before"), "t_after": p_w.get("t_after")},
                })

            # Rule 3: sender balance delta must match
            o_s_delta = int(o_w.get("s_after", 0)) - int(o_w.get("s_before", 0))
            p_s_delta = int(p_w.get("s_after", 0)) - int(p_w.get("s_before", 0))
            if o_s_delta != p_s_delta:
                ok = False
                failed_calls.append({
                    "index": i,
                    "sender": who,
                    "reason": "sender_balance_delta_mismatch",
                    "call": call,
                    "original_delta": o_s_delta,
                    "patched_delta": p_s_delta,
                    "original": {"s_before": o_w.get("s_before"), "s_after": o_w.get("s_after")},
                    "patched":  {"s_before": p_w.get("s_before"), "s_after": p_w.get("s_after")},
                })

    # Global balance delta sanity
    if int(orig.get("global_balance", {}).get("delta", 0)) != int(pat.get("global_balance", {}).get("delta", 0)):
        ok = False
        failed_calls.append({
            "reason": "global_balance_delta_changed",
            "original_global": orig.get("global_balance", {}),
            "patched_global":  pat.get("global_balance", {}),
        })

    return {
        "ok": ok,
        "reason": None if ok else "benign_regression_failed",
        "original": orig,
        "patched": pat,
        "failed_calls": failed_calls,
    }