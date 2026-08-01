#!/usr/bin/env python3
"""
solidifi_score.py — Evaluate baseline patches on SolidiFI cases (v2)
=====================================================================
Fixed for SolidiFI semantics:
  - Interface check EXCLUDES injected bug functions (_re_ent, _intou, etc.)
  - Mitigation checks whether the TARGET injected function was fixed/removed
  - A repair that removes injected bugs while keeping host functions = correct

USAGE:
  python solidifi_score.py \
      --manifest solidifi_pilot20.json \
      --tool solgpt \
      --baselines-dir results/solidifi_baselines \
      --out results/solidifi_scores \
      --solc ~/.solcx/solc-v0.5.12
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TOOLS = ["solgpt", "sguard", "sguardplus", "smartfix", "tips",
         "elysium", "smartshield", "invguard"]

INVGUARD_CLASS_LABELS = {
    "reentrancy": "Reentrancy",
    "integer_overflow": "Arithmetic",
    "unchecked_call": "Unchecked calls",
    "tx_origin": "tx.origin",
}

# SolidiFI injection suffixes — functions matching these are injected bugs,
# NOT part of the original host contract interface.
INJECTION_SUFFIXES = re.compile(
    r"_re_ent\d*$|_intou\d*$|_unchk_send\d*$|_unchk\d*$|_txorigin\d*$|"
    r"^bug_re_ent\d*$|^bug_intou\d*$|^bug_unchk\d*$|^bug_unchk_send\d*$|"
    r"^bug_txorigin\d*$|"
    r"^callme_re_ent\d*$|^buyTicket_re_ent\d*$|^claimReward_re_ent\d*$|"
    r"^withdrawBalance_re_ent\d*$|^withdraw_balances_re_ent\d*$|"
    r"^withdrawFunds_re_ent\d*$|"
    r"^transfer_intou\d*$|^withdraw_intou\d*$|^increaseLockTime_intou\d*$|"
    r"^transfer_undrflow\d*$|^withdraw_ovrflow\d*$|"
    r"^my_func_unchk\d*$|^my_func_uncheck\d*$|^cash_unchk\d*$|"
    r"^callnotchecked_unchk\d*$|^unhandledsend_unchk\d*$|"
    r"^sendToWinner_unchk\d*$|^withdrawBal_unchk\d*$|"
    r"^withdrawLeftOver_unchk\d*$|^UncheckedExternalCall_unchk\d*$|"
    r"^sendto_txorigin\d*$|^withdrawAll_txorigin\d*$|"
    r"^transferTo_txorigin\d*$|^multiTransfer$|^timeOf$"
)


def is_injected_function(fn_name):
    return bool(INJECTION_SUFFIXES.search(fn_name))


def extract_functions(source):
    return set(re.findall(r"function\s+(\w+)\s*\(", source))


def extract_host_functions(source):
    all_fns = extract_functions(source)
    return {fn for fn in all_fns if not is_injected_function(fn)}


def extract_injected_functions(source):
    all_fns = extract_functions(source)
    return {fn for fn in all_fns if is_injected_function(fn)}


def check_compilation(sol_path, solc_bin="solc"):
    try:
        proc = subprocess.run(
            [solc_bin, "--combined-json", "bin", str(sol_path)],
            capture_output=True, text=True, timeout=30)
        return proc.returncode == 0
    except FileNotFoundError:
        return _try_solcx_compile(sol_path)
    except Exception:
        return False


def _try_solcx_compile(sol_path):
    try:
        import solcx
        src = Path(sol_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"pragma\s+solidity\s+\^?(\d+\.\d+\.\d+)", src)
        ver = m.group(1) if m else "0.5.12"
        try:
            solcx.install_solc(ver)
        except Exception:
            pass
        solcx.compile_source(src, solc_version=ver)
        return True
    except Exception:
        return False


def check_interface_preserved(original_path, patched_path):
    try:
        orig = Path(original_path).read_text(encoding="utf-8", errors="replace")
        patched = Path(patched_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False, "read_error", {}

    orig_contracts = set(re.findall(r"contract\s+(\w+)", orig))
    patch_contracts = set(re.findall(r"contract\s+(\w+)", patched))
    if not orig_contracts & patch_contracts:
        return False, "contract_name_changed", {}

    orig_host_fns = extract_host_functions(orig)
    patch_all_fns = extract_functions(patched)

    missing_host = orig_host_fns - patch_all_fns
    if missing_host:
        return False, f"host_functions_removed:{','.join(sorted(missing_host))}", {
            "host_fns_in_orig": len(orig_host_fns),
            "missing": sorted(missing_host),
        }

    orig_injected = extract_injected_functions(orig)
    removed_injected = orig_injected - patch_all_fns
    return True, "ok", {
        "host_fns_in_orig": len(orig_host_fns),
        "injected_in_orig": len(orig_injected),
        "injected_removed": len(removed_injected),
        "injected_remaining": len(orig_injected & patch_all_fns),
    }


def check_pragma_preserved(original_path, patched_path):
    try:
        orig = Path(original_path).read_text(encoding="utf-8", errors="replace")
        patched = Path(patched_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return True
    orig_m = re.search(r"pragma\s+solidity\s+([^;]+);", orig)
    patch_m = re.search(r"pragma\s+solidity\s+([^;]+);", patched)
    if orig_m and patch_m:
        orig_major = re.search(r"(\d+)\.(\d+)", orig_m.group(1))
        patch_major = re.search(r"(\d+)\.(\d+)", patch_m.group(1))
        if orig_major and patch_major:
            if int(patch_major.group(2)) >= 8 and int(orig_major.group(2)) < 8:
                return False
    return True


def check_mitigation(original_path, patched_path, vuln_class, target_fn):
    try:
        orig = Path(original_path).read_text(encoding="utf-8", errors="replace")
        patched = Path(patched_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False, "read_error"

    patch_fns = extract_functions(patched)

    if target_fn not in patch_fns:
        return True, "target_removed"

    orig_body = _extract_fn_body(orig, target_fn)
    patch_body = _extract_fn_body(patched, target_fn)
    if not orig_body or not patch_body:
        return False, "body_extraction_failed"

    orig_norm = re.sub(r"\s+", " ", orig_body).strip()
    patch_norm = re.sub(r"\s+", " ", patch_body).strip()
    if orig_norm == patch_norm:
        return False, "target_unchanged"

    return _check_vuln_pattern_fixed(orig_body, patch_body, vuln_class)


def _extract_fn_body(source, fn_name):
    pattern = rf"function\s+{re.escape(fn_name)}\s*\("
    m = re.search(pattern, source)
    if not m:
        return None
    depth = 0
    started = False
    start = m.start()
    for i in range(start, min(start + 3000, len(source))):
        if source[i] == "{":
            depth += 1
            started = True
        elif source[i] == "}":
            depth -= 1
            if started and depth == 0:
                return source[start:i + 1]
    return source[start:start + 500]


def _check_vuln_pattern_fixed(orig_body, patch_body, vuln_class):
    if vuln_class == "reentrancy":
        has_lock = bool(re.search(
            r"(reentrancyLock|locked|_notEntered|nonReentrant|mutex)",
            patch_body))
        if has_lock:
            return True, "reentrancy_guard_added"

        orig_call = _find_pos(orig_body, r"\.(call|send)\s*[.(]")
        orig_state = _find_pos(orig_body, r"\w+\s*(\-=|\+=|=\s*0)")
        patch_call = _find_pos(patch_body, r"\.(call|send)\s*[.(]")
        patch_state = _find_pos(patch_body, r"\w+\s*(\-=|\+=|=\s*0)")

        if (orig_call is not None and orig_state is not None
                and orig_call < orig_state):
            if (patch_state is not None and patch_call is not None
                    and patch_state < patch_call):
                return True, "checks_effects_interactions"
            if patch_call is None and ".transfer(" in patch_body:
                return True, "call_replaced_with_transfer"

        if (".call.value(" in orig_body and
                ".call.value(" not in patch_body and
                ".transfer(" in patch_body):
            return True, "call_replaced"

        return False, "modified_but_unclear"

    elif vuln_class == "integer_overflow":
        if "SafeMath" in patch_body and "SafeMath" not in orig_body:
            return True, "safemath_added"
        if (".add(" in patch_body or ".sub(" in patch_body or
                ".mul(" in patch_body):
            if ".add(" not in orig_body and ".sub(" not in orig_body:
                return True, "safemath_ops"
        patch_req = len(re.findall(r"require\s*\(", patch_body))
        orig_req = len(re.findall(r"require\s*\(", orig_body))
        if patch_req > orig_req:
            return True, "require_guard_added"
        return False, "modified_but_unclear"

    elif vuln_class == "unchecked_call":
        if "require" in patch_body and "require" not in orig_body:
            return True, "return_checked"
        if re.search(r"bool\s+\w+\s*=.*\.(send|call)", patch_body):
            if re.search(r"require\s*\(\s*\w+", patch_body):
                return True, "return_checked"
        return False, "modified_but_unclear"

    elif vuln_class == "tx_origin":
        if "tx.origin" in orig_body and "tx.origin" not in patch_body:
            if "msg.sender" in patch_body:
                return True, "txorigin_to_msgsender"
            return True, "txorigin_removed"
        return False, "modified_but_unclear"

    return False, "unknown_class"


def _find_pos(text, pattern):
    m = re.search(pattern, text)
    return m.start() if m else None


def compute_patch_size(original_path, patched_path):
    try:
        orig = Path(original_path).read_text(
            encoding="utf-8", errors="replace").splitlines()
        patch = Path(patched_path).read_text(
            encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    orig_set = set(l.strip() for l in orig if l.strip())
    patch_set = set(l.strip() for l in patch if l.strip())
    return {
        "orig_lines": len(orig),
        "patch_lines": len(patch),
        "added": len(patch_set - orig_set),
        "removed": len(orig_set - patch_set),
    }


def find_patch(baselines_dir, tool, stem):
    candidates = [
        Path(baselines_dir) / tool / f"{stem}.sol",
        Path(baselines_dir) / tool / stem / "patched.sol",
        Path(baselines_dir) / tool / stem / f"{stem}.sol",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    tool_dir = Path(baselines_dir) / tool
    if tool_dir.is_dir():
        stem_dir = tool_dir / stem
        if stem_dir.is_dir():
            sols = list(stem_dir.glob("*.sol"))
            if sols:
                return str(sols[0])
    return None


def score_tool(manifest, baselines_dir, tool, solc_bin="solc"):
    results = []
    for entry in manifest:
        stem = entry["stem"]
        orig_path = entry["contract"]
        vuln_class = entry["extra_env"].get("INVGUARD_VULN_CLASS", "unknown")
        target_fn = entry["target_function"]

        rec = {
            "stem": stem, "tool": tool, "vuln_class": vuln_class,
            "host_id": entry.get("host_id", ""),
            "target_fn": target_fn,
            "patch_found": False, "compiles": False,
            "interface_ok": False, "pragma_ok": True,
            "mitigated": False, "mitigation_method": "",
            "effective": False,
            "injected_removed": 0, "injected_remaining": 0,
        }

        patch_path = find_patch(baselines_dir, tool, stem)
        if not patch_path:
            results.append(rec)
            continue
        rec["patch_found"] = True
        rec["patch_file"] = patch_path

        rec["compiles"] = check_compilation(patch_path, solc_bin)
        if not rec["compiles"]:
            results.append(rec)
            continue

        iface_ok, iface_reason, iface_detail = check_interface_preserved(
            orig_path, patch_path)
        rec["interface_ok"] = iface_ok
        rec["interface_reason"] = iface_reason
        rec["injected_removed"] = iface_detail.get("injected_removed", 0)
        rec["injected_remaining"] = iface_detail.get("injected_remaining", 0)

        rec["pragma_ok"] = check_pragma_preserved(orig_path, patch_path)

        mit, method = check_mitigation(orig_path, patch_path,
                                        vuln_class, target_fn)
        rec["mitigated"] = bool(mit)
        rec["mitigation_method"] = method

        rec["patch_size"] = compute_patch_size(orig_path, patch_path)

        rec["effective"] = (
            rec["compiles"] and rec["interface_ok"]
            and rec["pragma_ok"] and rec["mitigated"]
        )
        results.append(rec)
    return results


def tabulate(all_results, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    by_tool = defaultdict(list)
    for r in all_results:
        by_tool[r["tool"]].append(r)

    classes = sorted(set(r["vuln_class"] for r in all_results))

    print(f"\n{'='*85}")
    print(f"  SolidiFI BASELINE COMPARISON — Pilot 20")
    print(f"{'='*85}")
    print(f"  {'Tool':15s} {'Patch':>8s} {'Compiles':>10s} {'HostIF':>8s} "
          f"{'Mitigated':>10s} {'Effective':>10s}")
    print(f"  {'-'*80}")

    summary_rows = []
    for tool in sorted(by_tool.keys()):
        recs = by_tool[tool]
        n = len(recs)
        patch = sum(1 for r in recs if r["patch_found"])
        comp = sum(1 for r in recs if r["compiles"])
        iface = sum(1 for r in recs if r["interface_ok"])
        mit = sum(1 for r in recs if r["mitigated"])
        eff = sum(1 for r in recs if r["effective"])

        print(f"  {tool:15s} {patch:>4d}/{n:<3d} {comp:>6d}/{n:<3d} "
              f"{iface:>4d}/{n:<3d} {mit:>6d}/{n:<3d} {eff:>6d}/{n:<3d}")
        summary_rows.append({
            "tool": tool, "n": n, "patch_generated": patch,
            "compiles": comp, "interface_ok": iface,
            "mitigated": mit, "effective": eff,
        })
    print(f"  {'-'*80}")

    print(f"\n{'='*85}")
    print(f"  PER-CLASS BREAKDOWN (effective / n)")
    print(f"{'='*85}")
    header = f"  {'Tool':15s}"
    for cls in classes:
        label = INVGUARD_CLASS_LABELS.get(cls, cls)[:14]
        header += f" {label:>15s}"
    print(header)
    print(f"  {'-'*80}")

    for tool in sorted(by_tool.keys()):
        row = f"  {tool:15s}"
        for cls in classes:
            cls_recs = [r for r in by_tool[tool] if r["vuln_class"] == cls]
            n = len(cls_recs)
            eff = sum(1 for r in cls_recs if r["effective"])
            row += f" {eff:>6d}/{n:<3d}     "
        print(row)
    print()

    print(f"{'='*85}")
    print(f"  PER-CONTRACT DETAIL")
    print(f"{'='*85}")
    for tool in sorted(by_tool.keys()):
        print(f"\n  [{tool}]")
        for r in by_tool[tool]:
            status = "OK " if r["effective"] else "---"
            comp_s = "C" if r["compiles"] else "."
            iface_s = "I" if r["interface_ok"] else "."
            mit_s = "M" if r["mitigated"] else "."
            method = r.get("mitigation_method", "")[:25]
            inj_rem = r.get("injected_removed", 0)
            inj_left = r.get("injected_remaining", 0)
            print(f"    {status} {r['stem']:55s} [{comp_s}{iface_s}{mit_s}] "
                  f"{method:25s} inj:-{inj_rem}/kept:{inj_left}")

    csv_path = out_dir / "solidifi_baseline_scores.csv"
    with open(csv_path, "w", newline="") as f:
        cols = ["tool", "stem", "vuln_class", "host_id", "target_fn",
                "patch_found", "compiles", "interface_ok", "pragma_ok",
                "mitigated", "mitigation_method", "effective",
                "injected_removed", "injected_remaining"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in all_results:
            w.writerow(r)
    print(f"\n  CSV: {csv_path}")

    json_path = out_dir / "solidifi_baseline_summary.json"
    with open(json_path, "w") as f:
        json.dump({"summary": summary_rows, "per_contract": all_results},
                  f, indent=2, default=str)
    print(f"  JSON: {json_path}")


def print_table_only(out_dir):
    json_path = Path(out_dir) / "solidifi_baseline_summary.json"
    if not json_path.is_file():
        print(f"No results at {json_path}")
        return
    data = json.load(open(json_path))
    tabulate(data["per_contract"], out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", help="solidifi_pilot20.json")
    ap.add_argument("--tool",
                    help=f"Tool name or 'all'. Options: {', '.join(TOOLS)}")
    ap.add_argument("--baselines-dir", default="results/solidifi_baselines")
    ap.add_argument("--out", default="results/solidifi_scores")
    ap.add_argument("--solc", default="solc")
    ap.add_argument("--print-table", action="store_true")
    args = ap.parse_args()

    if args.print_table:
        print_table_only(args.out)
        return

    if not args.manifest or not args.tool:
        ap.error("--manifest and --tool required (or use --print-table)")

    manifest = json.load(open(args.manifest))
    tools = TOOLS if args.tool == "all" else [args.tool.lower()]

    all_results = []
    for tool in tools:
        print(f"\nScoring {tool} ...", flush=True)
        results = score_tool(manifest, args.baselines_dir, tool, args.solc)
        all_results.extend(results)

    tabulate(all_results, args.out)


if __name__ == "__main__":
    main()
