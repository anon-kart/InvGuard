#!/usr/bin/env python3
"""
score_rq2.py — Read RQ2 results and print the table
====================================================
Run this after run_rq2.py finishes. It reads the results/<tag>/
directories and produces:
  1. The RQ2 headline table (gate-ON accept rate vs gate-OFF false-accept)
  2. Per-contract breakdown showing where gate-OFF admitted false accepts
  3. Per-class breakdown

USAGE:
  cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"
  python score_rq2.py
  python score_rq2.py --models gpt-4o-mini,gpt-5-mini,gpt-5.5
"""
import argparse
import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODELS = ["gpt-4o-mini", "gpt-5-mini", "gpt-5.5"]


def load_manifest(path):
    with open(path) as f:
        return json.load(f)


def classify_stem(stem):
    if stem.startswith("acces"):
        return "access_control"
    elif stem.startswith("integ"):
        return "integer_overflow"
    elif stem.startswith("bad_r"):
        return "bad_randomness"
    elif stem.startswith("denia"):
        return "denial_of_service"
    elif stem.startswith("reent"):
        return "reentrancy"
    elif stem.startswith("unche"):
        return "unchecked_call"
    return "unknown"


def read_tag(tag):
    summary_path = os.path.join(REPO_ROOT, "results", tag, "_batch_summary.json")
    if not os.path.isfile(summary_path):
        return None
    data = json.load(open(summary_path))
    results = []
    for r in data:
        stem = r["stem"]
        gate = r.get("gate", {})
        accepted = gate.get("accepted", False)
        reason = gate.get("reason", "")
        verdicts = gate.get("verdicts", {})

        gate_skipped = False
        gate_would_have_accepted = None
        real_arbitration = {}

        vr_path = os.path.join(REPO_ROOT, "results", tag, stem,
                               "flow2_outputs", "patch_validation",
                               "validation_report.json")
        if os.path.isfile(vr_path):
            try:
                vr = json.load(open(vr_path))
                gate_skipped = vr.get("gate_skipped", False)
                gate_would_have_accepted = vr.get("gate_would_have_accepted")
                real_arbitration = vr.get("arbitration", {})
            except Exception:
                pass

        results.append({
            "stem": stem,
            "vuln_class": classify_stem(stem),
            "accepted": accepted,
            "reason": reason,
            "gate_skipped": gate_skipped,
            "gate_would_have_accepted": gate_would_have_accepted,
            "verdicts": verdicts,
            "real_arbitration": real_arbitration,
        })
    return results


def print_headline_table(models, all_data):
    print(f"\n{'='*72}")
    print("  RQ2 — Gate vs Model (/20 contracts)")
    print(f"{'='*72}")
    print(f"  {'Backbone':20s} {'gate-ON accept':>18s}  {'gate-OFF false-accept':>24s}")
    print(f"  {'-'*66}")

    for model in models:
        tag_on = f"rq2_{model.replace('.', '_')}_gate_on"
        tag_off = f"rq2_{model.replace('.', '_')}_gate_off"
        data_on = all_data.get(tag_on)
        data_off = all_data.get(tag_off)

        if data_on:
            n = len(data_on)
            acc = sum(1 for r in data_on if r["accepted"])
            on_str = f"{acc}/{n} ({100*acc/n:.1f}%)"
        else:
            on_str = "(not run)"

        if data_off:
            n = len(data_off)
            fa = sum(1 for r in data_off
                     if r["gate_skipped"] and r["gate_would_have_accepted"] is False)
            total_accepted = sum(1 for r in data_off if r["accepted"])
            off_str = f"{fa}/{total_accepted} ({100*fa/total_accepted:.1f}%)" if total_accepted else f"{fa}/0"
        else:
            off_str = "(not run)"

        print(f"  {model:20s} {on_str:>18s}  {off_str:>24s}")

    print(f"  {'='*66}\n")


def print_per_class(models, all_data):
    classes = ["access_control", "integer_overflow", "bad_randomness",
               "denial_of_service", "reentrancy", "unchecked_call"]

    print(f"{'='*80}")
    print("  RQ2 — Per-class gate-ON accept counts")
    print(f"{'='*80}")
    header = f"  {'Class':20s}"
    for m in models:
        header += f" {m:>14s}"
    print(header)
    print(f"  {'-'*76}")

    for cls in classes:
        row = f"  {cls:20s}"
        for model in models:
            tag = f"rq2_{model.replace('.', '_')}_gate_on"
            data = all_data.get(tag)
            if data:
                cls_items = [r for r in data if r["vuln_class"] == cls]
                n = len(cls_items)
                acc = sum(1 for r in cls_items if r["accepted"])
                row += f" {acc:>5d}/{n:<3d}     "
            else:
                row += f" {'—':>14s}"
        print(row)
    print()


def print_false_accept_details(models, all_data):
    print(f"{'='*80}")
    print("  RQ2 — Gate-OFF false-accept details")
    print(f"{'='*80}")
    for model in models:
        tag = f"rq2_{model.replace('.', '_')}_gate_off"
        data = all_data.get(tag)
        if not data:
            continue
        fas = [r for r in data
               if r["gate_skipped"] and r["gate_would_have_accepted"] is False]
        if not fas:
            print(f"  {model}: 0 false accepts")
            continue
        print(f"\n  {model}: {len(fas)} false accept(s)")
        for r in fas:
            arb = r.get("real_arbitration", {})
            print(f"    {r['stem']:50s}  "
                  f"replay={arb.get('replay_verdict','?')}  "
                  f"inv={arb.get('invariant_verdict','?')}  "
                  f"benign={arb.get('benign_verdict','?')}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",")]

    all_data = {}
    found_any = False
    for model in models:
        for gate in ["gate_on", "gate_off"]:
            tag = f"rq2_{model.replace('.', '_')}_gate_on" if gate == "gate_on" \
                  else f"rq2_{model.replace('.', '_')}_gate_off"
            data = read_tag(tag)
            if data:
                all_data[tag] = data
                found_any = True

    if not found_any:
        print("No RQ2 results found. Run run_rq2.py first.")
        sys.exit(1)

    print_headline_table(models, all_data)
    print_per_class(models, all_data)
    print_false_accept_details(models, all_data)


if __name__ == "__main__":
    main()
