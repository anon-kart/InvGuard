#!/usr/bin/env python3
"""
reclassify.py  —  rebuild _accepts.csv from logs ALREADY on disk (no rerun)
===========================================================================
Reads results/<tag>/<stem>/{flow1.log,flow2.log,flow2_outputs/...} and rewrites
results/<tag>/_accepts.csv with a PRECISE reason per contract:

  ok                              accepted by the strict gate
  gate_rejected                   patch built, gate ran, patch failed a check
  flow2_no_impactful_exploit      attacks ran but none moved value (correct decline)
  flow1_no_verified_invariants    Flow-1 produced no usable invariant
  flow1_z3_infra_fail             Z3 checker infra error
  crash_see_log                   uncaught traceback
  no_report                       unknown / none of the above

USAGE:
  python reclassify.py --tag tier3_icse
"""
import argparse, json, os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def classify_from_logs(stem_dir):
    txt = ""
    for lp in (os.path.join(stem_dir, "flow2.log"),
               os.path.join(stem_dir, "flow1.log")):
        if os.path.isfile(lp):
            txt += open(lp, encoding="utf-8", errors="ignore").read()
    if "No verified-useful invariants" in txt:
        return "flow1_no_verified_invariants"
    if ("no executable impactful exploit" in txt
            or "No repair claim is made" in txt
            or "none had concrete impact" in txt):
        return "flow2_no_impactful_exploit"
    if "Z3Checker failed" in txt or "[FLOW1] Checker failed" in txt:
        return "flow1_z3_infra_fail"
    if "Traceback (most recent call last)" in txt:
        return "crash_see_log"
    return "no_report"


def read_gate(stem_dir):
    vr = os.path.join(stem_dir, "flow2_outputs", "patch_validation",
                      "validation_report.json")
    if not os.path.isfile(vr):
        return {"accepted": False, "reason": classify_from_logs(stem_dir),
                "verdicts": {}}
    try:
        d = json.load(open(vr))
    except Exception as e:
        return {"accepted": False, "reason": f"bad_json:{e}", "verdicts": {}}
    arb = d.get("arbitration", {}) or {}
    acc = bool(d.get("ok", False))
    return {"accepted": acc, "reason": "ok" if acc else "gate_rejected",
            "verdicts": {"replay": arb.get("replay_verdict"),
                         "invariant": arb.get("invariant_verdict"),
                         "benign": arb.get("benign_verdict")}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()
    res_root = os.path.join(REPO_ROOT, "results", args.tag)
    summ_p = os.path.join(res_root, "_batch_summary.json")
    summary = json.load(open(summ_p)) if os.path.isfile(summ_p) else []

    rows = []
    for r in summary:
        sd = os.path.join(res_root, r["stem"])
        g = read_gate(sd)
        r["gate"] = g
        rows.append((r["stem"], r["target_function"], g))

    # rewrite both files
    json.dump(summary, open(summ_p, "w"), indent=2)
    with open(os.path.join(res_root, "_accepts.csv"), "w") as f:
        f.write("stem,target_function,accepted,reason,replay,invariant,benign\n")
        for stem, tf, g in rows:
            v = g["verdicts"]
            f.write(f"{stem},{tf},{g['accepted']},{g['reason']},"
                    f"{v.get('replay')},{v.get('invariant')},{v.get('benign')}\n")

    # tally + grouped print
    from collections import Counter
    c = Counter(g["reason"] for _, _, g in rows)
    n = len(rows); acc = c.get("ok", 0)
    print(f"\n========== {args.tag}: {acc}/{n} strict accepts ==========")
    order = ["ok", "gate_rejected", "flow2_no_impactful_exploit",
             "flow1_no_verified_invariants", "flow1_z3_infra_fail",
             "crash_see_log", "no_report"]
    for reason in order:
        members = [stem for stem, _, g in rows if g["reason"] == reason]
        if members:
            print(f"\n[{reason}]  ({len(members)})")
            for m in members:
                print(f"    {m}")


if __name__ == "__main__":
    main()
