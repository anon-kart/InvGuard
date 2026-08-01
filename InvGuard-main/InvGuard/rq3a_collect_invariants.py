#!/usr/bin/env python3
"""
rq3a_collect_invariants.py — RQ3(a): Collect invariants for annotation
=======================================================================
Extracts all invariants from Flow-1 outputs, along with their Z3 verdicts,
into a CSV for manual annotation by two reviewers.

PROBLEM: run_batch.py currently does NOT snapshot flow1_verified_invariants/.
So this script does TWO things:

  Step 1 (--patch-snapshot): Patches run_batch.py to also snapshot
          flow1_verified_invariants/ alongside flow1/ and flow2/.

  Step 2 (--collect): After running experiments with the patched run_batch.py,
          extracts invariants from results/<tag>/<stem>/flow1_invariants/
          into a CSV at results/rq3a_invariants.csv

  Step 3 (--kappa): After two annotators fill in the CSV, computes Cohen's kappa.

USAGE:
  cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"

  # Step 1: patch run_batch.py (one-time)
  python rq3a_collect_invariants.py --patch-snapshot

  # Step 2: re-run one gate-ON cell to capture invariants
  python run_rq2.py --manifest manifest_subset20.json --models gpt-4o-mini --gates gate_on

  # Step 3: extract invariants into CSV
  python rq3a_collect_invariants.py --collect --tag rq2_gpt-4o-mini_gate_on

  # Step 4: two annotators fill columns annotator1_correct and annotator2_correct (Y/N)
  # Step 5: compute kappa
  python rq3a_collect_invariants.py --kappa --csv results/rq3a_invariants.csv
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def patch_snapshot():
    rb_path = os.path.join(REPO_ROOT, "run_batch.py")
    with open(rb_path, "r") as f:
        src = f.read()

    if "flow1_verified_invariants" in src:
        print("[patch] run_batch.py already snapshots flow1_verified_invariants, skipping.")
        return

    old = '''def _snapshot(dst):
    """Copy current run_outputs/flow1 and flow2 into the per-contract result dir."""
    for sub in ("flow1", "flow2"):
        src = os.path.join(RUN_OUT, sub)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, f"{sub}_outputs"),
                            dirs_exist_ok=True)'''

    new = '''def _snapshot(dst):
    """Copy current run_outputs/flow1, flow2, and flow1_verified_invariants."""
    for sub in ("flow1", "flow2"):
        src = os.path.join(RUN_OUT, sub)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, f"{sub}_outputs"),
                            dirs_exist_ok=True)
    inv_src = os.path.join(RUN_OUT, "flow1_verified_invariants")
    if os.path.isdir(inv_src):
        shutil.copytree(inv_src, os.path.join(dst, "flow1_invariants"),
                        dirs_exist_ok=True)'''

    if old not in src:
        print("[patch] ERROR: cannot find _snapshot function in run_batch.py.")
        print("        The function signature may have changed.")
        sys.exit(1)

    src = src.replace(old, new, 1)
    with open(rb_path, "w") as f:
        f.write(src)
    print("[patch] Patched run_batch.py to also snapshot flow1_verified_invariants.")


def collect_invariants(tag, out_csv):
    results_dir = os.path.join(REPO_ROOT, "results", tag)
    summary_path = os.path.join(results_dir, "_batch_summary.json")
    if not os.path.isfile(summary_path):
        print(f"No results for {tag}")
        sys.exit(1)

    data = json.load(open(summary_path))
    rows = []

    for r in data:
        stem = r["stem"]
        inv_dir = os.path.join(results_dir, stem, "flow1_invariants")
        if not os.path.isdir(inv_dir):
            print(f"  [skip] {stem}: no flow1_invariants/ (re-run with patched run_batch.py)")
            continue

        summary_file = os.path.join(inv_dir, "invariant_summary.json")
        if os.path.isfile(summary_file):
            try:
                inv_summary = json.load(open(summary_file))
            except Exception:
                inv_summary = {}
        else:
            inv_summary = {}

        for category in ["VT", "VU", "VM", "UT"]:
            cat_data = inv_summary.get(category, {})
            invs = cat_data.get("examples", [])
            for inv_text in invs:
                z3_verdict = {
                    "VT": "VERIFIED_TRUE",
                    "VU": "VERIFIED_USEFUL",
                    "VM": "VERIFIED_MUTANT",
                    "UT": "UNTESTED",
                }.get(category, category)

                rows.append({
                    "id": len(rows) + 1,
                    "contract": stem,
                    "invariant": inv_text.strip(),
                    "z3_category": category,
                    "z3_verdict": z3_verdict,
                    "annotator1_correct": "",
                    "annotator2_correct": "",
                    "notes": "",
                })

        for suffix in ["VT", "VU"]:
            for fn_tag in ["all", "deposit", "withdraw",
                           "deposit.refined", "withdraw.refined"]:
                txt_file = os.path.join(inv_dir, f"invariants.{fn_tag}.{suffix}.txt")
                if not os.path.isfile(txt_file):
                    continue
                with open(txt_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        already = any(row["invariant"] == line and row["contract"] == stem
                                      for row in rows)
                        if not already:
                            rows.append({
                                "id": len(rows) + 1,
                                "contract": stem,
                                "invariant": line,
                                "z3_category": suffix,
                                "z3_verdict": "VERIFIED_TRUE" if suffix == "VT" else "VERIFIED_USEFUL",
                                "annotator1_correct": "",
                                "annotator2_correct": "",
                                "notes": f"from {fn_tag}.{suffix}.txt",
                            })

    if not rows:
        print("No invariants found. Did you run with the patched run_batch.py?")
        sys.exit(1)

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "contract", "invariant", "z3_category", "z3_verdict",
            "annotator1_correct", "annotator2_correct", "notes"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nExtracted {len(rows)} invariants from {len(data)} contracts.")
    print(f"Saved to: {out_csv}")
    print(f"\nNext: two annotators fill annotator1_correct and annotator2_correct (Y/N),")
    print(f"then run: python rq3a_collect_invariants.py --kappa --csv {out_csv}")

    by_cat = defaultdict(int)
    for row in rows:
        by_cat[row["z3_category"]] += 1
    print(f"\nBreakdown: {dict(by_cat)}")


def compute_kappa(csv_path):
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    annotated = [(r["annotator1_correct"].strip().upper(),
                  r["annotator2_correct"].strip().upper())
                 for r in rows
                 if r["annotator1_correct"].strip() and r["annotator2_correct"].strip()]

    if not annotated:
        print("No annotated rows found. Fill annotator1_correct and annotator2_correct first.")
        return

    n = len(annotated)
    agree = sum(1 for a, b in annotated if a == b)
    p_o = agree / n

    a1_y = sum(1 for a, _ in annotated if a == "Y") / n
    a2_y = sum(1 for _, b in annotated if b == "Y") / n
    a1_n = 1 - a1_y
    a2_n = 1 - a2_y
    p_e = (a1_y * a2_y) + (a1_n * a2_n)

    if p_e == 1.0:
        kappa = 1.0
    else:
        kappa = (p_o - p_e) / (1 - p_e)

    z3_correct = sum(1 for r in rows
                     if r["annotator1_correct"].strip().upper() == "Y"
                     and r["annotator2_correct"].strip().upper() == "Y")
    z3_false_accept = sum(1 for r in rows
                          if r["z3_category"] in ("VT", "VU", "VM")
                          and r["annotator1_correct"].strip().upper() == "N"
                          and r["annotator2_correct"].strip().upper() == "N")
    z3_false_reject = sum(1 for r in rows
                          if r["z3_category"] == "UT"
                          and r["annotator1_correct"].strip().upper() == "Y"
                          and r["annotator2_correct"].strip().upper() == "Y")

    print(f"\nRQ3(a) — Z3 Verdict Accuracy")
    print(f"{'='*50}")
    print(f"  Annotated invariants:  {n}")
    print(f"  Agreement (p_o):       {p_o:.3f}")
    print(f"  Expected (p_e):        {p_e:.3f}")
    print(f"  Cohen's kappa:         {kappa:.3f}")
    print()
    print(f"  Z3 correct (both Y):   {z3_correct}")
    print(f"  Z3 false-accept:       {z3_false_accept}")
    print(f"  Z3 false-reject:       {z3_false_reject}")
    print()

    if kappa >= 0.81:
        print(f"  Interpretation: almost perfect agreement")
    elif kappa >= 0.61:
        print(f"  Interpretation: substantial agreement")
    elif kappa >= 0.41:
        print(f"  Interpretation: moderate agreement")
    else:
        print(f"  Interpretation: fair or poor agreement")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch-snapshot", action="store_true",
                    help="Patch run_batch.py to snapshot invariants")
    ap.add_argument("--collect", action="store_true",
                    help="Extract invariants from results into CSV")
    ap.add_argument("--kappa", action="store_true",
                    help="Compute Cohen's kappa from annotated CSV")
    ap.add_argument("--tag", default="rq2_gpt-4o-mini_gate_on")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    if args.patch_snapshot:
        patch_snapshot()
    elif args.collect:
        out_csv = args.csv or os.path.join(REPO_ROOT, "results", "rq3a_invariants.csv")
        collect_invariants(args.tag, out_csv)
    elif args.kappa:
        csv_path = args.csv or os.path.join(REPO_ROOT, "results", "rq3a_invariants.csv")
        compute_kappa(csv_path)
    else:
        print("Specify --patch-snapshot, --collect, or --kappa. See --help.")


if __name__ == "__main__":
    main()
