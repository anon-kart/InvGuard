#!/usr/bin/env python3
"""
solidifi_fix_targets.py — Fix target functions in the pilot manifest
=====================================================================
SolidiFI injects bug functions with distinctive naming suffixes:
  _re_ent      (reentrancy)
  _intou       (integer overflow/underflow)
  _unchk_send  (unchecked send)
  _unchk       (unhandled exceptions — general unchecked pattern)
  _txorigin    (tx.origin misuse)
  bug_unchk_send  (alternative unchecked send naming)
  bug_txorigin    (alternative tx.origin naming)

This script reads each contract, finds ALL injected functions, picks
the most exploitable one per case, and updates the manifest.

USAGE:
  python solidifi_fix_targets.py --manifest solidifi_pilot20.json

Also prints a diagnostic showing every injected function found per file,
which injected function was selected, and why.
"""
import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# Injection suffix patterns per InvGuard class
INJECTION_PATTERNS = {
    "reentrancy": [
        r"function\s+(withdraw\w*_re_ent\d*)\s*\(",
        r"function\s+(\w+_re_ent\d*)\s*\(",
        r"function\s+(callme_re_ent\d*)\s*\(",
        r"function\s+(buyTicket_re_ent\d*)\s*\(",
        r"function\s+(claimReward_re_ent\d*)\s*\(",
    ],
    "integer_overflow": [
        r"function\s+(transfer_intou\d*)\s*\(",
        r"function\s+(\w+_intou\d*)\s*\(",
        r"function\s+(bug_intou\d*)\s*\(",
        r"function\s+(increaseLockTime_intou\d*)\s*\(",
    ],
    "unchecked_call": [
        r"function\s+(bug_unchk_send\d*)\s*\(",
        r"function\s+(\w+_unchk_send\d*)\s*\(",
        r"function\s+(bug_unchk\d*)\s*\(",
        r"function\s+(\w+_unchk\d*)\s*\(",
        r"function\s+(callnotchecked_unchk\d*)\s*\(",
        r"function\s+(my_func_unchk\d*)\s*\(",
        r"function\s+(unhandledsend_unchk\d*)\s*\(",
        r"function\s+(UncsijekemyFunc\d*)\s*\(",
    ],
    "tx_origin": [
        r"function\s+(bug_txorigin\d*)\s*\(",
        r"function\s+(\w+_txorigin\d*)\s*\(",
        r"function\s+(withdrawAll_txorigin\d*)\s*\(",
        r"function\s+(sendto_txorigin\d*)\s*\(",
        r"function\s+(transferTo_txorigin\d*)\s*\(",
    ],
}

# Preference scoring for picking the best injected function
# Higher = better for exploitation
EXPLOIT_QUALITY = {
    "reentrancy": {
        # Functions with .call.value() and balance mapping are best
        "call_value_balance": 10,    # msg.sender.call.value(balances[...])
        "call_value_generic": 7,     # .call.value() without mapping
        "send_with_state": 5,        # .send() with some state
        "send_simple": 3,            # simple .send()
        "generic": 1,
    },
    "integer_overflow": {
        "balance_underflow": 10,     # balances[x] -= amount (underflow)
        "locktime_overflow": 8,      # lockTime += value (overflow)
        "transfer_overflow": 7,      # transfer with unchecked math
        "generic_arithmetic": 3,
        "generic": 1,
    },
    "unchecked_call": {
        "send_state_update": 10,     # .send() followed by state change
        "call_ignored": 8,           # .call() return ignored
        "send_ignored": 6,           # .send() return ignored
        "generic": 1,
    },
    "tx_origin": {
        "withdraw_txorigin": 10,     # tx.origin guarding withdraw/transfer
        "sendto_txorigin": 8,        # tx.origin guarding sendTo
        "owner_change": 6,           # tx.origin for ownership
        "generic": 3,
    },
}


def find_injected_functions(source, vuln_class):
    """Find all injected functions in a file for the given class."""
    found = []
    for pattern in INJECTION_PATTERNS.get(vuln_class, []):
        for m in re.finditer(pattern, source):
            fn_name = m.group(1)
            if fn_name not in [f["name"] for f in found]:
                # Extract the function body (approximate)
                start = m.start()
                body = _extract_function_body(source, start)
                quality = _score_function(fn_name, body, vuln_class)
                found.append({
                    "name": fn_name,
                    "line": source[:start].count("\n") + 1,
                    "quality": quality,
                    "body_preview": body[:200],
                })
    return found


def _extract_function_body(source, fn_start):
    """Extract approximate function body from start position."""
    depth = 0
    started = False
    end = fn_start
    for i in range(fn_start, min(fn_start + 2000, len(source))):
        ch = source[i]
        if ch == "{":
            depth += 1
            started = True
        elif ch == "}":
            depth -= 1
            if started and depth == 0:
                end = i + 1
                break
    return source[fn_start:end]


def _score_function(fn_name, body, vuln_class):
    """Score a function's exploit quality."""
    name_lower = fn_name.lower()
    body_lower = body.lower()

    if vuln_class == "reentrancy":
        if ".call.value(" in body and ("balances" in body_lower or
                                        "balance" in body_lower or
                                        "credit" in body_lower):
            return 10
        if ".call.value(" in body:
            return 7
        if ".send(" in body and ("balances" in body_lower or
                                  "counter" in body_lower):
            return 5
        if ".send(" in body:
            return 3
        return 1

    elif vuln_class == "integer_overflow":
        if "-=" in body and ("balance" in body_lower or
                              "balances" in body_lower):
            return 10
        if "+=" in body and "locktime" in body_lower:
            return 8
        if "transfer" in name_lower and ("-=" in body or "+=" in body):
            return 7
        if "-=" in body or "+=" in body:
            return 3
        return 1

    elif vuln_class == "unchecked_call":
        if ".send(" in body:
            # Check if return value is actually ignored
            if "bool" not in body and "require" not in body:
                if "=" in body.split(".send(")[0].split("\n")[-1]:
                    return 6  # assigned but not checked
                return 10  # completely ignored
            return 4
        if ".call(" in body or ".call.value(" in body:
            if "require" not in body:
                return 8
            return 3
        return 1

    elif vuln_class == "tx_origin":
        if "withdraw" in name_lower or "send" in name_lower:
            return 10
        if "transfer" in name_lower:
            return 8
        if "tx.origin" in body:
            return 6
        return 1

    return 1


def fix_manifest(manifest_path):
    """Read manifest, fix target functions, write back."""
    manifest = json.load(open(manifest_path))
    print(f"Fixing {len(manifest)} entries in {manifest_path}\n")

    fixed_count = 0
    for entry in manifest:
        sol_path = entry["contract"]
        vuln_class = entry["extra_env"]["INVGUARD_VULN_CLASS"]
        old_tf = entry["target_function"]

        if not os.path.isfile(sol_path):
            print(f"  SKIP {entry['stem']}: file not found")
            continue

        source = Path(sol_path).read_text(encoding="utf-8", errors="replace")
        injected = find_injected_functions(source, vuln_class)

        if not injected:
            print(f"  WARN {entry['stem']}: no injected functions found "
                  f"(patterns: {vuln_class})")
            # Fall back: try all patterns
            for cls, patterns in INJECTION_PATTERNS.items():
                for pattern in patterns:
                    for m in re.finditer(pattern, source):
                        injected.append({
                            "name": m.group(1),
                            "quality": 1,
                            "body_preview": "",
                        })
            if injected:
                print(f"         found {len(injected)} from other classes: "
                      f"{[f['name'] for f in injected]}")

        if not injected:
            print(f"  KEEP {entry['stem']}: {old_tf} (no injection found)")
            continue

        # Pick the highest-quality injected function
        injected.sort(key=lambda f: f["quality"], reverse=True)
        best = injected[0]

        if best["name"] != old_tf:
            entry["target_function"] = best["name"]
            fixed_count += 1
            status = "FIXED"
        else:
            status = "OK   "

        print(f"  {status} {entry['stem']}")
        print(f"         {old_tf} → {best['name']} "
              f"(quality={best['quality']}, "
              f"{len(injected)} injected fns found)")
        if len(injected) > 1:
            others = [f"{f['name']}(q={f['quality']})"
                      for f in injected[1:4]]
            print(f"         alternatives: {', '.join(others)}")

    # Write back
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone: {fixed_count}/{len(manifest)} entries updated")
    print(f"Manifest written: {manifest_path}")

    # Print final summary
    print(f"\nFinal manifest:")
    for entry in manifest:
        cls = entry["extra_env"]["INVGUARD_VULN_CLASS"]
        print(f"  {cls:20s} | {entry['target_function']:35s} | "
              f"{Path(entry['contract']).name}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="solidifi_pilot20.json")
    args = ap.parse_args()
    fix_manifest(args.manifest)
