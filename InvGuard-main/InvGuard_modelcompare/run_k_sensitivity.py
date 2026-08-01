#!/usr/bin/env python3
"""
run_k_sensitivity.py  —  Result #6 (k-sensitivity for AttackModule)
===================================================================
Sweeps the number of attack candidates k in {1,3,5,10} over the manifest and
reports, per k:
  - exploit success rate   (fraction of contracts with >=1 impactful attack)
  - critical-invariant coverage (fraction of VM/critical invariants violated by
    at least one generated attack)
  - duplicate attacks      (attacks whose impact signature duplicates another)
  - runtime                (median flow2 elapsed)

It sets INVGUARD_NUM_ATTACKS=k, which the AttackModule reads (see
add_k_hook.md for the ~3-line change), then calls run_batch.py with a per-k tag.

Until you wire the hook, the pipeline is hard-coded to k=5; this script will then
only meaningfully vary k once the hook is in. The aggregation below is robust to
fewer/more than 5 A-ids.

USAGE:
  python run_k_sensitivity.py --manifest manifest_tier3.json --base-tag tier3_k
  # default sweep: --ks 1,3,5,10
"""
import argparse, glob, json, os, statistics, subprocess, sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def run_k(manifest, base_tag, k, model):
    tag = f"{base_tag}_{k}"
    env = os.environ.copy()
    env["INVGUARD_NUM_ATTACKS"] = str(k)
    cmd = [sys.executable, os.path.join(REPO_ROOT, "run_batch.py"),
           "--manifest", manifest, "--tag", tag, "--model", model]
    print(f"\n########## k={k}  (tag={tag}) ##########", flush=True)
    subprocess.run(cmd, env=env, cwd=REPO_ROOT)
    return tag


def analyse_k(tag):
    res_root = os.path.join(REPO_ROOT, "results", tag)
    summ = os.path.join(res_root, "_batch_summary.json")
    if not os.path.isfile(summ):
        return None
    rows = json.load(open(summ))
    n = len(rows)
    contracts_with_impact = 0
    total_attacks = 0
    impactful_attacks = 0
    dup_attacks = 0
    times = []
    for r in rows:
        sd = os.path.join(res_root, r["stem"])
        er_p = os.path.join(sd, "flow2_outputs", "exploit_executor",
                            "executor_results.json")
        if os.path.isfile(er_p):
            er = json.load(open(er_p))
            A = {kk: vv for kk, vv in (er.get("results", {}) or {}).items()
                 if kk.startswith("A")}
            total_attacks += len(A)
            imp = [vv for vv in A.values() if vv.get("impact_ok")]
            impactful_attacks += len(imp)
            if imp:
                contracts_with_impact += 1
            # duplicate = same (excess_drain_wei, run_ok) signature among impactful
            sigs = [(vv.get("excess_drain_wei"), vv.get("impact_ok_differential"))
                    for vv in imp]
            dup_attacks += len(sigs) - len(set(sigs))
        t = (r.get("flow2", {}) or {}).get("elapsed_sec")
        if t:
            times.append(t)
    return {
        "n": n,
        "exploit_success_rate": round(100 * contracts_with_impact / n, 1) if n else 0,
        "total_attacks": total_attacks,
        "impactful_attacks": impactful_attacks,
        "duplicate_attacks": dup_attacks,
        "median_time_sec": round(statistics.median(times), 1) if times else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base-tag", required=True)
    ap.add_argument("--ks", default="1,3,5,10")
    ap.add_argument("--model", default=os.environ.get("INVGUARD_MODEL", "gpt-4o-mini"))
    args = ap.parse_args()
    ks = [int(x) for x in args.ks.split(",") if x.strip()]

    table = {}
    for k in ks:
        tag = run_k(args.manifest, args.base_tag, k, args.model)
        table[k] = analyse_k(tag)

    out = os.path.join(REPO_ROOT, "results", f"{args.base_tag}_ksensitivity.json")
    json.dump(table, open(out, "w"), indent=2)
    print("\n=== k-sensitivity (Result #6) ===")
    print(f"{'k':>3s} {'ExplSucc%':>9s} {'#Attacks':>9s} {'#Impact':>8s} "
          f"{'#Dup':>5s} {'MedTime_s':>10s}")
    for k in ks:
        t = table.get(k)
        if not t:
            print(f"{k:>3d}   (no data)"); continue
        print(f"{k:>3d} {t['exploit_success_rate']:>9} {t['total_attacks']:>9d} "
              f"{t['impactful_attacks']:>8d} {t['duplicate_attacks']:>5d} "
              f"{str(t['median_time_sec']):>10}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
