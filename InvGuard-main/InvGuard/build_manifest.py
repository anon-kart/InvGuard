#!/usr/bin/env python3
"""
build_manifest.py  -  emit a run_batch manifest from a folder of .sol files.

Scans a directory for Solidity files and writes a manifest in the same schema
run_batch.py already consumes (stem, contract, target_function, extra_env with
INVGUARD_VULN_CLASS). The target function is chosen by heuristic and can be
overridden per file or globally.

Usage:
  python build_manifest.py --src datasets/invcon246 --out manifest_invcon.json \
      --vuln-class arithmetic --target-hint transfer
  python build_manifest.py --src datasets/trace2inv --out manifest_trace2inv.json \
      --vuln-class reentrancy
"""
import argparse
import glob
import json
import os
import re

STATE_CHANGING = re.compile(
    r"function\s+(\w+)\s*\([^)]*\)\s*(?:public|external)"
    r"(?:(?!\bview\b|\bpure\b).)*?(?:\{|returns)",
    re.DOTALL)

PREFERRED = ["transfer", "transferFrom", "withdraw", "redeem", "borrow",
             "deposit", "claim", "swap", "mint", "burn", "approve"]


def pick_target(src_text, hint):
    fns = STATE_CHANGING.findall(src_text)
    if hint:
        for f in fns:
            if f.lower() == hint.lower():
                return f
    for p in PREFERRED:
        for f in fns:
            if f.lower() == p:
                return f
    return fns[0] if fns else "constructor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="directory of .sol files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--vuln-class", default="arithmetic",
                    help="INVGUARD_VULN_CLASS for every entry")
    ap.add_argument("--target-hint", default="",
                    help="preferred target function name if present")
    ap.add_argument("--contract-prefix", default="",
                    help="path prefix written into the manifest 'contract' field")
    ap.add_argument("--txn-dir", default="",
                    help="if set, attach INVGUARD_TXN_FILE per contract when a "
                         "matching <stem>.json/.txt trace exists here")
    ap.add_argument("--meta-dir", default="",
                    help="if set, attach INVGUARD_META_FILE per contract likewise")
    args = ap.parse_args()

    sols = sorted(glob.glob(os.path.join(args.src, "**", "*.sol"), recursive=True))
    manifest = []
    for path in sols:
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            text = ""
        target = pick_target(text, args.target_hint)
        contract_field = (os.path.join(args.contract_prefix, os.path.basename(path))
                          if args.contract_prefix else path)
        extra = {"INVGUARD_VULN_CLASS": args.vuln_class}
        if args.txn_dir:
            for ext in (".json", ".txt"):
                cand = os.path.join(args.txn_dir, stem + ext)
                if os.path.isfile(cand):
                    extra["INVGUARD_TXN_FILE"] = cand
                    break
        if args.meta_dir:
            for ext in (".json", ".txt"):
                cand = os.path.join(args.meta_dir, stem + ext)
                if os.path.isfile(cand):
                    extra["INVGUARD_META_FILE"] = cand
                    break
        manifest.append({
            "stem": stem,
            "contract": contract_field,
            "target_function": target,
            "extra_env": extra,
        })

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"[manifest] {len(manifest)} contracts -> {args.out}")
    miss = [m["stem"] for m in manifest if m["target_function"] == "constructor"]
    if miss:
        print(f"[manifest] {len(miss)} had no clear target function "
              f"(set to 'constructor'): {miss[:8]}")


if __name__ == "__main__":
    main()
