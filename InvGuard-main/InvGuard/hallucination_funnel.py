#!/usr/bin/env python3
"""
hallucination_funnel.py  —  Result #3 (LLM hallucination filtering)
===================================================================
Builds the ICSE funnel table: how many RAW LLM outputs are rejected by each
NON-LLM check (parser/compiler, SMT/Z3, Foundry replay) at each stage
(invariant gen, attack gen, patch gen).

It reads the per-contract snapshots created by run_batch.py:
  results/<tag>/<stem>/flow1_outputs/...
  results/<tag>/<stem>/flow2_outputs/...

This script counts ARTIFACTS THE PIPELINE ALREADY EMITS. It does not re-run
anything. If a count is missing for a stem, it is reported as such so you can
see coverage rather than silently zero-filling.

USAGE:
  python hallucination_funnel.py --tag tier3_icse
Outputs results/<tag>/_hallucination_funnel.{json,csv} and prints the table.
"""
import argparse, glob, json, os, re

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_json(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def _count_lines(p):
    if not os.path.isfile(p):
        return 0
    return sum(1 for ln in open(p, encoding="utf-8", errors="ignore")
               if ln.strip())


def invariant_stage(stem_dir):
    """
    Flow-1 buckets the LLM's candidate invariants into VU/VM/VT/UT after Z3.
    Raw   = candidates the LLM proposed (invariants.forced.*.debug.json or
            invariants.txt).
    Rej-parser = candidates dropped before Z3 (malformed / unparseable).
    Rej-SMT    = candidates Z3 falsified (rejected file).
    Accepted   = VU + VM (verified) [+ VT trusted, counted separately].
    """
    f1 = os.path.join(stem_dir, "flow1_outputs")
    vinv = os.path.join(stem_dir, "flow2_outputs")  # flow1 verified copied here too

    raw = 0
    for dj in glob.glob(os.path.join(f1, "invariants.forced.*.debug.json")):
        d = _load_json(dj)
        if isinstance(d, dict):
            raw += len(d.get("candidates", d.get("raw", []) or [])) or 0
        elif isinstance(d, list):
            raw += len(d)
    if raw == 0:
        raw = _count_lines(os.path.join(f1, "invariants.txt"))

    rej_parser = 0
    for ft in glob.glob(os.path.join(f1, "invariants.forced.*.filtered.txt")):
        # filtered.txt = survived parser; parser rejects = raw - filtered (>=0)
        pass
    filtered = sum(_count_lines(p) for p in
                   glob.glob(os.path.join(f1, "invariants.forced.*.filtered.txt")))
    if raw and filtered:
        rej_parser = max(raw - filtered, 0)

    rej_smt = sum(_count_lines(p) for p in
                  glob.glob(os.path.join(f1, "verified_invariants.*.rejected.txt")))

    # Accepted verified (VU/VM). Look in the verified_invariants snapshot.
    vdir = os.path.join(stem_dir, "flow2_outputs", "..")  # fallback
    accepted = sum(_count_lines(p) for p in
                   glob.glob(os.path.join(f1, "verified_invariants.*.txt"))
                   if "rejected" not in p and "summary" not in p)

    return {"raw": raw, "rej_parser": rej_parser, "rej_smt": rej_smt,
            "rej_replay": None, "accepted": accepted}


def attack_stage(stem_dir):
    """
    Flow-2 AttackModule emits A1..A5 candidate attacker contracts, then Foundry
    compiles+runs them. executor_results.json carries compile_ok/run_ok/impact_ok.
    Raw        = total_attacks (LLM-proposed).
    Rej-parser = compile_fail (didn't compile = malformed Solidity).
    Rej-replay = compiled+ran but impact_ok=0 (no real exploit -> hallucinated).
    Accepted   = impact_ok count (genuinely impactful attacks).
    """
    er = _load_json(os.path.join(stem_dir, "flow2_outputs",
                                 "exploit_executor", "executor_results.json"))
    if not er:
        return {"raw": None, "rej_parser": None, "rej_smt": None,
                "rej_replay": None, "accepted": None}
    results = er.get("results", {}) or {}
    A = {k: v for k, v in results.items() if k.startswith("A")}
    raw = er.get("total_attacks") or len(A)
    compile_fail = sum(1 for v in A.values() if not v.get("compile_ok"))
    impactful = sum(1 for v in A.values() if v.get("impact_ok"))
    ran_no_impact = sum(1 for v in A.values()
                        if v.get("compile_ok") and not v.get("impact_ok"))
    return {"raw": raw, "rej_parser": compile_fail, "rej_smt": None,
            "rej_replay": ran_no_impact, "accepted": impactful}


def patch_stage(stem_dir):
    """
    Flow-2 FixMaker proposes a patch; the non-LLM gate then checks
    compile -> Z3 invariants -> Foundry replay -> benign regression.
    We count one patch attempt per round from validation_report.json.
    Raw        = patch rounds attempted (>=1).
    Rej-parser = rounds where patch failed compile / wrong API.
    Rej-SMT    = rounds where invariant_verdict == FAIL.
    Rej-replay = rounds where replay_verdict == FAIL.
    Accepted   = 1 if final gate ok else 0.
    """
    vr = _load_json(os.path.join(stem_dir, "flow2_outputs",
                                 "patch_validation", "validation_report.json"))
    if not vr:
        return {"raw": 0, "rej_parser": None, "rej_smt": None,
                "rej_replay": None, "accepted": 0}
    arb = vr.get("arbitration", {}) or {}
    inv = vr.get("invariants", {}) or {}
    accepted = 1 if vr.get("ok") else 0
    rej_parser = 1 if inv.get("reason") in ("WRONG_CONTRACT_NAME",
                                            "MISSING_TARGET_FUNCTION",
                                            "API_COMPAT_FAILED") else 0
    rej_smt = 1 if arb.get("invariant_verdict") == "FAIL" else 0
    rej_replay = 1 if arb.get("replay_verdict") == "FAIL" else 0
    return {"raw": 1, "rej_parser": rej_parser, "rej_smt": rej_smt,
            "rej_replay": rej_replay, "accepted": accepted}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()
    res_root = os.path.join(REPO_ROOT, "results", args.tag)
    stems = [d for d in sorted(os.listdir(res_root))
             if os.path.isdir(os.path.join(res_root, d)) and not d.startswith("_")]

    agg = {s: {"raw": 0, "rej_parser": 0, "rej_smt": 0, "rej_replay": 0,
               "accepted": 0, "missing": 0} for s in ("invariant", "attack", "patch")}
    per_contract = {}

    for stem in stems:
        sd = os.path.join(res_root, stem)
        rows = {"invariant": invariant_stage(sd),
                "attack": attack_stage(sd),
                "patch": patch_stage(sd)}
        per_contract[stem] = rows
        for stage, r in rows.items():
            for k in ("raw", "rej_parser", "rej_smt", "rej_replay", "accepted"):
                v = r.get(k)
                if v is None:
                    continue
                agg[stage][k] += v

    # Print + CSV
    csv_path = os.path.join(res_root, "_hallucination_funnel.csv")
    with open(csv_path, "w") as f:
        f.write("stage,raw_llm_outputs,rejected_parser_compiler,rejected_smt,"
                "rejected_foundry_replay,accepted\n")
        for stage in ("invariant", "attack", "patch"):
            a = agg[stage]
            f.write(f"{stage},{a['raw']},{a['rej_parser']},{a['rej_smt']},"
                    f"{a['rej_replay']},{a['accepted']}\n")
    json.dump({"aggregate": agg, "per_contract": per_contract},
              open(os.path.join(res_root, "_hallucination_funnel.json"), "w"),
              indent=2)

    print("\n=== Hallucination-filtering funnel (Result #3) ===")
    print(f"{'Stage':12s} {'RawLLM':>7s} {'RejParse':>9s} {'RejSMT':>7s} "
          f"{'RejReplay':>10s} {'Accept':>7s}")
    for stage in ("invariant", "attack", "patch"):
        a = agg[stage]
        print(f"{stage:12s} {a['raw']:7d} {a['rej_parser']:9d} {a['rej_smt']:7d} "
              f"{a['rej_replay']:10d} {a['accepted']:7d}")
    print(f"\nWrote {csv_path}")


if __name__ == "__main__":
    main()
