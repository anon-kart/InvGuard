#!/usr/bin/env python3
"""
run_ablations.py  —  Result #4 (baselines & ablations) + Result #5 (runtime)
============================================================================
Runs InvGuard in several configurations over the SAME manifest, by toggling the
env flags the pipeline ALREADY reads. No pipeline logic is faked.

Configurations (each is a real run; nothing is hand-edited afterward):

  full            : invariant-guided + SMT + FixChecker gate   (the paper system)
  direct_llm      : INVGUARD_ALLOW_CONTRACT_ONLY=1
                    -> FixMaker patches with NO Flow-1 invariants (direct GPT repair)
  no_smt          : INVGUARD_USE_VM_AS_CONSTRAINTS=0 + skip Flow-1 verify reuse
                    -> invariants proposed but NOT SMT-promoted as obligations
  no_replay       : INVGUARD_SKIP_REPLAY=1  (see patch in add_ablation_hooks.md)
                    -> gate keeps invariant+benign checks but not Foundry replay
  no_fixchecker   : INVGUARD_SKIP_GATE=1    (see patch in add_ablation_hooks.md)
                    -> accept FixMaker's first patch with no non-LLM gate

The last two need two ~5-line hooks added to flow_2_files/agent.py
(see add_ablation_hooks.md). full / direct_llm / no_smt work with the code as-is.

Per configuration it calls run_batch.py with a distinct tag, then aggregates
strict-accept counts and median runtime into one comparison table.

USAGE:
  python run_ablations.py --manifest manifest_tier3.json --base-tag tier3
  # add --configs full,direct_llm  to run a subset
"""
import argparse, json, os, statistics, subprocess, sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

CONFIGS = {
    "full":          {},
    "direct_llm":    {"INVGUARD_ALLOW_CONTRACT_ONLY": "1"},
    "no_smt":        {"INVGUARD_USE_VM_AS_CONSTRAINTS": "0"},
    "no_replay":     {"INVGUARD_SKIP_REPLAY": "1"},
    "no_fixchecker": {"INVGUARD_SKIP_GATE": "1"},
}


def run_cfg(manifest, base_tag, cfg, model):
    tag = f"{base_tag}_{cfg}"
    env = os.environ.copy()
    for k, v in CONFIGS[cfg].items():
        env[k] = v
    # direct_llm has no Flow-1 obligations; still run Flow-1 so invariant-precision
    # column is populated, but Flow-2 ignores them.
    cmd = [sys.executable, os.path.join(REPO_ROOT, "run_batch.py"),
           "--manifest", manifest, "--tag", tag, "--model", model]
    print(f"\n########## CONFIG: {cfg}  (tag={tag}) ##########", flush=True)
    subprocess.run(cmd, env=env, cwd=REPO_ROOT)
    return tag


def tally(tag):
    res = os.path.join(REPO_ROOT, "results", tag, "_batch_summary.json")
    if not os.path.isfile(res):
        return None
    d = json.load(open(res))
    n = len(d)
    acc = sum(1 for r in d if r.get("gate", {}).get("accepted"))
    times = [r["flow2"]["elapsed_sec"] for r in d
             if r.get("flow2", {}).get("elapsed_sec")]
    return {"n": n, "accepts": acc,
            "accept_rate": round(100 * acc / n, 1) if n else 0,
            "median_time_sec": round(statistics.median(times), 1) if times else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base-tag", required=True)
    ap.add_argument("--model", default=os.environ.get("INVGUARD_MODEL", "gpt-4o-mini"))
    ap.add_argument("--configs", default="full,direct_llm,no_smt,no_replay,no_fixchecker")
    args = ap.parse_args()

    chosen = [c.strip() for c in args.configs.split(",") if c.strip()]
    table = {}
    for cfg in chosen:
        if cfg not in CONFIGS:
            print(f"!! unknown config {cfg}, skipping"); continue
        tag = run_cfg(args.manifest, args.base_tag, cfg, args.model)
        table[cfg] = tally(tag)

    out = os.path.join(REPO_ROOT, "results", f"{args.base_tag}_ablation_table.json")
    json.dump(table, open(out, "w"), indent=2)
    print("\n=== Ablation / baseline table (Result #4 + runtime #5) ===")
    print(f"{'Config':16s} {'Accepts':>8s} {'Rate%':>7s} {'MedTime_s':>10s}")
    for cfg in chosen:
        t = table.get(cfg)
        if not t:
            print(f"{cfg:16s}   (no data)"); continue
        print(f"{cfg:16s} {t['accepts']:>3d}/{t['n']:<4d} {t['accept_rate']:>7} "
              f"{str(t['median_time_sec']):>10}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
