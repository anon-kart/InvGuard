#!/usr/bin/env python3
"""
patch_validation_table.py  —  Result #2 (multi-metric patch validation)
=======================================================================
Turns InvGuard's per-contract gate reports into the ICSE multi-metric table:

  Tool | Patch generated | Compiles | Exploit blocked | Benign pass |
       | Invariants hold | Gas overhead | Median time

For InvGuard, every column is read from artifacts the gate ALREADY produces:
  - Patch generated : a FIXED_CONTRACT block was emitted
  - Compiles        : patched contract compiled under Foundry
  - Exploit blocked : replay_verdict == PASS (original exploit no longer impacts)
  - Benign pass     : benign_verdict == PASS (differential regression)
  - Invariants hold : invariant_verdict == PASS
  - Time            : flow2 elapsed_sec from _batch_summary.json

Gas overhead is the one column the current gate does NOT emit; this script
computes it if a gas snapshot exists (see add_gas_probe.md), else marks "n/a".

USAGE:
  python patch_validation_table.py --tag tier3_icse
Writes results/<tag>/_patch_validation_table.{json,csv}.

The baseline-tool rows (sGuard, SmartFix, ...) are NOT auto-filled here — you run
those tools separately on the SAME contracts and paste their numbers into the CSV.
This script gives you the InvGuard row computed from real runs, plus an empty
template for baselines so the table is apples-to-apples.
"""
import argparse, json, os, statistics

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BASELINES = ["sGuard", "sGuardPlus", "SmartFix", "TIPS", "Elysium",
             "SmartShield", "SolGPT"]


def _load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()
    res_root = os.path.join(REPO_ROOT, "results", args.tag)
    summary = _load(os.path.join(res_root, "_batch_summary.json")) or []

    rows = []
    times = []
    n = len(summary)
    gen = comp = blocked = benign = invok = gas_vals = 0
    gas_list = []
    for r in summary:
        sd = os.path.join(res_root, r["stem"])
        vr = _load(os.path.join(sd, "flow2_outputs", "patch_validation",
                                "validation_report.json")) or {}
        arb = vr.get("arbitration", {}) or {}
        has_patch = os.path.isfile(os.path.join(
            sd, "flow2_outputs", "approved_fixes", "approved_fix_latest.sol")) \
            or bool(vr)
        # Compile signal: any replay result with compile_ok, or invariants ran.
        replay = (vr.get("replay", {}) or {}).get("results", {}) or {}
        compiled = any(v.get("compile_ok") for v in replay.values()) or \
            bool((vr.get("invariants", {}) or {}).get("ok"))
        blk = arb.get("replay_verdict") == "PASS"
        bgn = arb.get("benign_verdict") == "PASS"
        ivk = arb.get("invariant_verdict") == "PASS"

        gas = None
        gp = os.path.join(sd, "flow2_outputs", "patch_validation", "gas_report.json")
        gd = _load(gp)
        if gd and "overhead_pct" in gd:
            gas = gd["overhead_pct"]
            gas_list.append(gas)

        t = (r.get("flow2", {}) or {}).get("elapsed_sec")
        if t:
            times.append(t)

        gen += 1 if has_patch else 0
        comp += 1 if compiled else 0
        blocked += 1 if blk else 0
        benign += 1 if bgn else 0
        invok += 1 if ivk else 0
        rows.append({"stem": r["stem"], "patch_generated": has_patch,
                     "compiles": compiled, "exploit_blocked": blk,
                     "benign_pass": bgn, "invariants_hold": ivk,
                     "gas_overhead_pct": gas, "time_sec": t,
                     "accepted": bool(vr.get("ok"))})

    invguard_row = {
        "tool": "InvGuard",
        "patch_generated": f"{gen}/{n}",
        "compiles": f"{comp}/{n}",
        "exploit_blocked": f"{blocked}/{n}",
        "benign_pass": f"{benign}/{n}",
        "invariants_hold": f"{invok}/{n}",
        "gas_overhead_pct": (round(statistics.mean(gas_list), 1)
                             if gas_list else "n/a"),
        "median_time_sec": round(statistics.median(times), 1) if times else "n/a",
    }

    out = {"invguard": invguard_row, "per_contract": rows,
           "baseline_template": [{"tool": b} for b in BASELINES]}
    json.dump(out, open(os.path.join(res_root, "_patch_validation_table.json"), "w"),
              indent=2)

    cols = ["tool", "patch_generated", "compiles", "exploit_blocked",
            "benign_pass", "invariants_hold", "gas_overhead_pct", "median_time_sec"]
    with open(os.path.join(res_root, "_patch_validation_table.csv"), "w") as f:
        f.write(",".join(cols) + "\n")
        for b in BASELINES:
            f.write(b + "," + ",".join([""] * (len(cols) - 1)) + "\n")
        f.write(",".join(str(invguard_row[c]) for c in cols) + "\n")

    print("\n=== Patch validation (Result #2) — InvGuard row ===")
    for c in cols:
        print(f"  {c:18s}: {invguard_row[c]}")
    print(f"\nBaselines ({', '.join(BASELINES)}) left blank — run them on the "
          f"same {n} contracts and paste into the CSV.")


if __name__ == "__main__":
    main()
