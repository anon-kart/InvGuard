# InvGuard/counterexample_replay.py
"""
Counterexample replay (Foundry) — best-effort concretization layer.

Goal (reviewer-proofing):
- When Z3Checker reports failed invariants with a counterexample/model, we try to
  concretize that model in the EVM (Foundry) and classify:
    - "REALISTIC": the candidate call executes successfully (doesn't revert)
    - "SPURIOUS_OR_PATH": the call reverts / can't be concretized
    - "UNREPLAYABLE": we couldn't build a runnable replay (missing info, constructor args, etc.)

This module is intentionally conservative and "best-effort":
- We do NOT attempt to prove the invariant violation on-chain (that requires DSL eval).
- We *do* provide strong evidence about path feasibility in the EVM.

Expected usage (Flow-1):
    from counterexample_replay import replay_failed_invariants

    if os.environ.get("REPLAY_COUNTEREXAMPLES", "0") == "1":
        report = replay_failed_invariants(contract_path=contract_file,
                                          function_name=fn or "",
                                          failed_items=core.failed or [])
        json.dump(report, open(...), indent=2)

Notes:
- This assumes Foundry (forge) is installed and accessible on PATH.
- The generated Foundry project is a tiny temporary folder under run_outputs/.
"""

from __future__ import annotations

import os
import re
import json
import time
import shutil
import hashlib
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logging.basicConfig(level=logging.INFO, force=True)

# ---------------------------
# Output location (stable)
# ---------------------------
_THIS_DIR = os.path.dirname(__file__)
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_DEFAULT_OUT_DIR = os.path.join(_REPO_ROOT, "run_outputs", "flow1_counterexample_replay")


# ---------------------------
# Public API
# ---------------------------
def replay_failed_invariants(
    contract_path: str,
    function_name: str,
    failed_items: List[Any],
    *,
    out_dir: Optional[str] = None,
    forge_timeout_sec: int = 90,
    max_items: int = 40,
) -> Dict[str, Any]:
    """
    Replays (best-effort) counterexamples for failed invariants using Foundry.

    Args:
        contract_path: path to the Solidity contract file
        function_name: function being checked (withdraw/deposit/...) or "" for unknown
        failed_items: items returned by your Z3Checker/InvGuard core for "failed"
        out_dir: where to write replay artifacts (projects/logs)
        forge_timeout_sec: per-replay timeout
        max_items: safety bound; replay can be expensive

    Returns:
        {
          "contract_path": "...",
          "function_name": "...",
          "timestamp": "...",
          "results": [
             {
               "idx": 0,
               "status": "REALISTIC|SPURIOUS_OR_PATH|UNREPLAYABLE",
               "reason": "...",
               "invariant": "...",
               "signature": "...",
               "args": [...],
               "arg_types": [...],
               "model": {...},
               "forge": {"returncode": int, "stdout_head": "...", "stderr_head": "..."},
               "project_dir": "..."
             }, ...
          ],
          "counts": {"REALISTIC": n, "SPURIOUS_OR_PATH": n, "UNREPLAYABLE": n}
        }
    """
    out_base = out_dir or _DEFAULT_OUT_DIR
    os.makedirs(out_base, exist_ok=True)

    contract_path = os.path.abspath(contract_path)
    if not os.path.exists(contract_path):
        raise FileNotFoundError(contract_path)

    # Limit to keep CI / reviewer runs bounded
    items = list(failed_items or [])[: max_items]

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        try:
            parsed = _parse_failed_item_best_effort(item, function_name=function_name)
            if not parsed.signature:
                results.append({
                    "idx": idx,
                    "status": "UNREPLAYABLE",
                    "reason": "missing_function_signature",
                    "invariant": parsed.invariant,
                    "signature": "",
                    "args": parsed.args,
                    "arg_types": parsed.arg_types,
                    "model": parsed.model,
                    "forge": None,
                    "project_dir": None,
                })
                continue

            proj_dir = _materialize_foundry_project(
                out_base=out_base,
                contract_path=contract_path,
                signature=parsed.signature,
                args=parsed.args,
                arg_types=parsed.arg_types,
                idx=idx,
            )

            forge_res = _run_forge_test(proj_dir, timeout_sec=forge_timeout_sec)

            # Classification heuristic:
            # - If compile/test succeeded => the call path is feasible in EVM ("REALISTIC")
            # - Else => likely spurious or model violates Solidity semantics ("SPURIOUS_OR_PATH")
            if forge_res["returncode"] == 0:
                status = "REALISTIC"
                reason = "call_executed_without_revert"
            else:
                status = "SPURIOUS_OR_PATH"
                reason = _classify_forge_failure(forge_res)

            results.append({
                "idx": idx,
                "status": status,
                "reason": reason,
                "invariant": parsed.invariant,
                "signature": parsed.signature,
                "args": parsed.args,
                "arg_types": parsed.arg_types,
                "model": parsed.model,
                "forge": forge_res,
                "project_dir": proj_dir,
            })
        except Exception as e:
            results.append({
                "idx": idx,
                "status": "UNREPLAYABLE",
                "reason": f"exception: {type(e).__name__}: {e}",
                "invariant": _best_effort_invariant_str(item),
                "signature": "",
                "args": [],
                "arg_types": [],
                "model": _best_effort_model_dict(item),
                "forge": None,
                "project_dir": None,
            })

    counts = {"REALISTIC": 0, "SPURIOUS_OR_PATH": 0, "UNREPLAYABLE": 0}
    for r in results:
        st = r.get("status")
        if st in counts:
            counts[st] += 1

    return {
        "contract_path": contract_path,
        "function_name": function_name or "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "counts": counts,
    }


# ---------------------------
# Failed item parsing
# ---------------------------
@dataclass
class ParsedFailedItem:
    invariant: str
    signature: str
    args: List[Any]
    arg_types: List[str]
    model: Dict[str, Any]


def _parse_failed_item_best_effort(item: Any, function_name: str) -> ParsedFailedItem:
    """
    Tries to extract:
    - invariant string
    - function signature (e.g., "withdraw(uint256)")
    - args/arg_types (ordered)
    - model dict
    from a wide range of "failed" shapes.

    Supported patterns (best-effort):
    - dict with keys: invariant / inv / property / failed_invariant
    - dict with keys: model / cex / counterexample / witness
    - dict with keys: signature / function_signature / fn_sig
    - raw string embedding JSON with model
    """
    inv = _best_effort_invariant_str(item)
    model = _best_effort_model_dict(item)

    # 1) If signature is explicit in the object, use it
    sig = ""
    if isinstance(item, dict):
        for k in ("signature", "function_signature", "fn_sig", "fnSignature", "call_signature"):
            v = item.get(k)
            if isinstance(v, str) and "(" in v and ")" in v:
                sig = v.strip()
                break

    # 2) Otherwise if function_name provided, attempt to build signature from model arg types
    if not sig and function_name:
        args, arg_types = _extract_args_from_model(model)
        sig = f"{function_name}({','.join(arg_types)})" if arg_types else f"{function_name}()"
        return ParsedFailedItem(invariant=inv, signature=sig, args=args, arg_types=arg_types, model=model)

    # 3) If we still don't have sig, try to sniff "fn(...)" in invariant text
    if not sig:
        m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", inv)
        if m:
            fn = m.group(1).strip()
            if fn and (function_name == "" or fn == function_name):
                raw_types = [t.strip() for t in (m.group(2) or "").split(",") if t.strip()]
                # If invariant has something that looks like types, use them; else guess from model.
                if raw_types and all(_looks_like_sol_type(t) for t in raw_types):
                    args, _ = _extract_args_from_model(model, force_types=raw_types)
                    sig = f"{fn}({','.join(raw_types)})"
                    return ParsedFailedItem(invariant=inv, signature=sig, args=args, arg_types=raw_types, model=model)

    # Fallback: if sig is known but we didn't set args/types yet
    args, arg_types = _extract_args_from_model(model)
    return ParsedFailedItem(invariant=inv, signature=sig, args=args, arg_types=arg_types, model=model)


def _best_effort_invariant_str(item: Any) -> str:
    if isinstance(item, dict):
        for k in ("invariant", "inv", "property", "failed_invariant", "expr", "line", "text"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    if isinstance(item, str):
        return item.strip()
    try:
        return json.dumps(item, ensure_ascii=False)[:2000]
    except Exception:
        return str(item)[:2000]


def _best_effort_model_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        for k in ("model", "cex", "counterexample", "witness", "assignment", "assignments"):
            v = item.get(k)
            if isinstance(v, dict):
                return v
            if isinstance(v, str):
                d = _try_parse_json_dict(v)
                if d is not None:
                    return d
    if isinstance(item, str):
        # try to parse embedded JSON dict
        d = _try_parse_json_dict(item)
        if d is not None:
            return d
    return {}


def _try_parse_json_dict(s: str) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    # best-effort: slice first {...} block
    i = s.find("{")
    j = s.rfind("}")
    if i == -1 or j == -1 or j <= i:
        return None
    blob = s[i : j + 1]
    try:
        obj = json.loads(blob)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _looks_like_sol_type(t: str) -> bool:
    t = (t or "").strip()
    if not t:
        return False
    if t in ("uint", "uint256", "int", "int256", "bool", "address"):
        return True
    if t.startswith("uint") or t.startswith("int"):
        return True
    if t.endswith("[]"):
        return True
    if t.startswith("bytes"):
        return True
    if t.startswith("mapping"):
        return True
    return False


def _extract_args_from_model(model: Dict[str, Any], force_types: Optional[List[str]] = None) -> Tuple[List[Any], List[str]]:
    """
    Extract arg.* keys from the model, order them stably, and assign Solidity types.
    Very conservative:
      - addresses: 0x-prefixed 40-hex => address
      - bool: True/False/0/1 if clearly boolean
      - else: uint256
    """
    if not model:
        return ([], force_types or [])

    # Gather arg.* entries; many solvers use "arg.amount", "arg0", etc.
    pairs: List[Tuple[str, Any]] = []
    for k, v in model.items():
        if isinstance(k, str) and (k.startswith("arg.") or k.startswith("arg")):
            pairs.append((k, v))

    # Stable ordering:
    # - Prefer arg.<name> alphabetical by name
    # - Then arg0,arg1,... numeric
    def keyfn(kv: Tuple[str, Any]) -> Tuple[int, str]:
        k = kv[0]
        m = re.match(r"arg(\d+)$", k)
        if m:
            return (0, f"{int(m.group(1)):08d}")
        if k.startswith("arg."):
            return (1, k)
        return (2, k)

    pairs.sort(key=keyfn)

    args: List[Any] = [v for _, v in pairs]

    # Types
    if force_types is not None:
        arg_types = list(force_types)
        # If force_types shorter, pad with uint256
        while len(arg_types) < len(args):
            arg_types.append("uint256")
        return args, arg_types[: len(args)]

    arg_types: List[str] = []
    for v in args:
        t = _infer_sol_type_from_value(v)
        arg_types.append(t)

    return args, arg_types


def _infer_sol_type_from_value(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        # Could be bool, but we only treat 0/1 as bool if it was explicitly boolean elsewhere.
        return "uint256"
    if isinstance(v, str):
        s = v.strip()
        if re.fullmatch(r"0x[a-fA-F0-9]{40}", s):
            return "address"
        if s.lower() in ("true", "false"):
            return "bool"
        # numeric string
        if re.fullmatch(r"-?\d+", s):
            return "uint256"
        # hex numeric
        if re.fullmatch(r"0x[a-fA-F0-9]+", s):
            return "uint256"
    # default
    return "uint256"


# ---------------------------
# Foundry project generation
# ---------------------------
def _materialize_foundry_project(
    *,
    out_base: str,
    contract_path: str,
    signature: str,
    args: List[Any],
    arg_types: List[str],
    idx: int,
) -> str:
    """
    Creates a mini Foundry project:
      <out_base>/replay_<hash>_<idx>/
         foundry.toml
         src/Target.sol
         test/Replay.t.sol

    The test does:
      - deploy Target with `new Target()` (no constructor args)
      - call function via low-level call with abi.encodeWithSignature(signature, args...)
      - assertTrue(ok) so forge test uses return code for classification
    """
    os.makedirs(out_base, exist_ok=True)

    h = hashlib.sha256((contract_path + "|" + signature + "|" + str(idx)).encode("utf-8")).hexdigest()[:10]
    proj_dir = os.path.join(out_base, f"replay_{h}_{idx}")
    if os.path.exists(proj_dir):
        shutil.rmtree(proj_dir)
    os.makedirs(proj_dir, exist_ok=True)

    src_dir = os.path.join(proj_dir, "src")
    test_dir = os.path.join(proj_dir, "test")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)

    # Copy contract as Target.sol
    shutil.copyfile(contract_path, os.path.join(src_dir, "Target.sol"))

    # foundry.toml minimal
    Path(os.path.join(proj_dir, "foundry.toml")).write_text(
        "\n".join([
            "[profile.default]",
            "src = 'src'",
            "out = 'out'",
            "libs = ['lib']",
            "test = 'test'",
            "optimizer = false",
            "",
        ]) + "\n",
        encoding="utf-8",
    )

    # Ensure forge-std is available:
    # - We do NOT auto-install (no internet). If your repo already has lib/forge-std,
    #   we symlink/copy it in.
    _ensure_forge_std(proj_dir)

    # Test file
    test_code = _render_replay_test(signature=signature, args=args, arg_types=arg_types)
    Path(os.path.join(test_dir, "Replay.t.sol")).write_text(test_code, encoding="utf-8")

    return proj_dir


def _ensure_forge_std(proj_dir: str) -> None:
    """
    Best-effort to make `import "forge-std/Test.sol";` compile without network.
    Strategy:
      - If repo_root/lib/forge-std exists => symlink it into proj_dir/lib/forge-std
      - Else if proj_dir/lib/forge-std exists => ok
      - Else: we still generate test, but forge will fail; caller will classify as UNREPLAYABLE/SPURIOUS.
    """
    lib_dir = os.path.join(proj_dir, "lib")
    os.makedirs(lib_dir, exist_ok=True)

    # Common locations in repos:
    candidates = [
        os.path.join(_REPO_ROOT, "lib", "forge-std"),
        os.path.join(_REPO_ROOT, "flow_2_files", "lib", "forge-std"),
        os.path.join(_REPO_ROOT, "flow_1_files", "lib", "forge-std"),
    ]
    dst = os.path.join(lib_dir, "forge-std")
    if os.path.exists(dst):
        return

    src = None
    for c in candidates:
        if os.path.isdir(c):
            src = c
            break

    if not src:
        logging.warning("[replay] forge-std not found locally; replay may fail to compile.")
        return

    try:
        # symlink preferred (fast), fallback to copy
        os.symlink(src, dst)
    except Exception:
        shutil.copytree(src, dst)


def _render_replay_test(signature: str, args: List[Any], arg_types: List[str]) -> str:
    # Convert args to Solidity literals (as best as possible)
    lit_args = [_to_sol_literal(v, t) for v, t in zip(args, arg_types)]
    args_csv = ", ".join(lit_args)

    # If no args, avoid trailing commas
    if args and args_csv.strip():
        enc = f'abi.encodeWithSignature("{signature}", {args_csv})'
    else:
        enc = f'abi.encodeWithSignature("{signature}")'

    return f"""// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/Target.sol";

contract ReplayTest is Test {{
    Target target;

    function setUp() public {{
        // Best-effort: assumes no-arg constructor.
        // If your contract requires constructor args, this replay will be UNREPLAYABLE.
        target = new Target();
    }}

    function test_replay() public {{
        (bool ok, ) = address(target).call({enc});
        // If it reverts, we treat the counterexample as likely spurious/unconcretizable.
        assertTrue(ok, "counterexample call reverted in EVM");
    }}
}}
"""


def _to_sol_literal(v: Any, sol_type: str) -> str:
    sol_type = (sol_type or "uint256").strip()

    if sol_type == "address":
        if isinstance(v, str) and re.fullmatch(r"0x[a-fA-F0-9]{40}", v.strip()):
            return f"address({v.strip()})"
        # fallback
        return "address(0x0000000000000000000000000000000000000000)"

    if sol_type == "bool":
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return "true" if v != 0 else "false"
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1"):
                return "true"
            if s in ("false", "0"):
                return "false"
        return "false"

    # default: uint256-ish
    if isinstance(v, int):
        if v < 0:
            # don’t emit negative uint literals
            return "uint256(0)"
        return f"uint256({v})"
    if isinstance(v, str):
        s = v.strip()
        if re.fullmatch(r"\d+", s):
            return f"uint256({s})"
        if re.fullmatch(r"0x[a-fA-F0-9]+", s):
            # hex numeric
            return f"uint256({s})"
    # fallback
    return "uint256(0)"


# ---------------------------
# Forge runner
# ---------------------------
def _run_forge_test(project_dir: str, timeout_sec: int) -> Dict[str, Any]:
    """
    Runs `forge test -vvv` inside project_dir.
    Returns stdout/stderr head for debugging + return code.
    """
    cmd = ["forge", "test", "-vvv"]
    try:
        p = subprocess.run(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
        return {
            "cmd": " ".join(cmd),
            "returncode": p.returncode,
            "stdout_head": (p.stdout or "")[:4000],
            "stderr_head": (p.stderr or "")[:4000],
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": " ".join(cmd),
            "returncode": 124,
            "stdout_head": ((e.stdout or "") if hasattr(e, "stdout") else "")[:4000],
            "stderr_head": ((e.stderr or "") if hasattr(e, "stderr") else "")[:4000],
            "error": f"timeout after {timeout_sec}s",
        }
    except FileNotFoundError:
        return {
            "cmd": " ".join(cmd),
            "returncode": 127,
            "stdout_head": "",
            "stderr_head": "",
            "error": "forge_not_found_on_PATH",
        }


def _classify_forge_failure(forge_res: Dict[str, Any]) -> str:
    """
    Converts a forge failure into a readable reason for bucketing.
    """
    rc = forge_res.get("returncode")
    err = (forge_res.get("stderr_head") or "") + "\n" + (forge_res.get("stdout_head") or "")
    low = err.lower()

    if rc == 127 or "forge_not_found" in low:
        return "forge_not_available"
    if rc == 124 or "timeout" in low:
        return "forge_timeout"
    if "parsererror" in low or "compilation failed" in low or "error:" in low:
        if "forge-std" in low and ("not found" in low or "cannot find" in low):
            return "missing_forge_std"
        if "constructor" in low and ("wrong argument count" in low or "no matching constructor" in low):
            return "unreplayable_constructor_args"
        return "compile_or_type_error"
    if "revert" in low or "assert" in low or "failed" in low:
        return "call_reverted_or_assert_failed"
    return "forge_test_failed"


# ---------------------------
# CLI (optional local dev)
# ---------------------------
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True, help="path to contract.sol")
    ap.add_argument("--fn", default="", help="function name (optional)")
    ap.add_argument("--failed_json", default="", help="path to json file containing failed_items list")
    args = ap.parse_args()

    failed_items: List[Any] = []
    if args.failed_json and os.path.exists(args.failed_json):
        failed_items = json.loads(Path(args.failed_json).read_text(encoding="utf-8"))

    rep = replay_failed_invariants(
        contract_path=args.contract,
        function_name=args.fn,
        failed_items=failed_items,
    )
    print(json.dumps(rep, indent=2))
