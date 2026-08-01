#!/usr/bin/env python3
"""
run_rq2.py — RQ2 gate-vs-model experiment driver
=================================================
Runs InvGuard on the 20-contract subset with multiple backbones and
gate ON / OFF to produce the RQ2 table.

Two columns in the table:
  gate-ON accept rate   — how many patches the deterministic gate accepted
  gate-OFF false-accept — patches auto-accepted that the gate WOULD have rejected

The thesis: gate-ON rate is roughly stable across backbones (reliability
comes from the gate, not the model), while gate-OFF admits false accepts.

USAGE:
  cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"
  # first apply the gate-skip patch (one-time):
  python patch_skip_gate.py
  # then run RQ2:
  python run_rq2.py --manifest manifest_subset20.json
  # run a single cell for debugging:
  python run_rq2.py --manifest manifest_subset20.json --models gpt-4o-mini --gates gate_on
"""
import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

DEFAULT_MODELS = ["gpt-4o-mini", "gpt-5-mini", "gpt-5.5"]
GATE_STATES = ["gate_on", "gate_off"]


def check_model_available(model):
    """Quick probe: send a tiny request to see if the model responds."""
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "reply with OK"}],
            max_tokens=5,
        )
        return True
    except Exception as e:
        print(f"  [model-check] {model} unavailable: {e}")
        return False


def run_cell(manifest, model, gate_state, skip_flow1=False):
    tag = f"rq2_{model.replace('.', '_')}_{gate_state}"
    env = os.environ.copy()
    env["INVGUARD_MODEL"] = model
    if gate_state == "gate_off":
        env["INVGUARD_SKIP_GATE"] = "1"
    else:
        env.pop("INVGUARD_SKIP_GATE", None)

    cmd = [sys.executable, os.path.join(REPO_ROOT, "run_batch.py"),
           "--manifest", manifest, "--tag", tag, "--model", model]
    if skip_flow1:
        cmd.append("--skip-flow1")

    print(f"\n{'='*65}", flush=True)
    print(f"  RQ2 CELL: model={model}  gate={gate_state}  tag={tag}", flush=True)
    print(f"{'='*65}", flush=True)
    subprocess.run(cmd, env=env, cwd=REPO_ROOT)
    return tag


def read_cell_results(tag):
    summary_path = os.path.join(REPO_ROOT, "results", tag, "_batch_summary.json")
    if not os.path.isfile(summary_path):
        return None
    data = json.load(open(summary_path))
    n = len(data)

    accepts = 0
    false_accepts = 0
    per_contract = []

    for r in data:
        gate = r.get("gate", {})
        stem = r["stem"]
        accepted = gate.get("accepted", False)
        if accepted:
            accepts += 1

        fa = False
        vr_path = os.path.join(REPO_ROOT, "results", tag, stem,
                               "flow2_outputs", "patch_validation",
                               "validation_report.json")
        if os.path.isfile(vr_path):
            try:
                vr = json.load(open(vr_path))
                if vr.get("gate_skipped") and not vr.get("gate_would_have_accepted"):
                    false_accepts += 1
                    fa = True
            except Exception:
                pass

        per_contract.append({
            "stem": stem,
            "accepted": accepted,
            "false_accept": fa,
            "reason": gate.get("reason", ""),
        })

    return {
        "n": n,
        "accepts": accepts,
        "accept_rate": round(100.0 * accepts / n, 1) if n else 0,
        "false_accepts": false_accepts,
        "false_accept_rate": round(100.0 * false_accepts / n, 1) if n else 0,
        "per_contract": per_contract,
    }


def print_rq2_table(models, results):
    print(f"\n{'='*70}")
    print("RQ2 — Gate vs Model (/20 contracts)")
    print(f"{'='*70}")
    print(f"{'Backbone':20s} {'gate-ON accept':>18s} {'gate-OFF false-accept':>24s}")
    print("-" * 70)
    for model in models:
        on = results.get(f"rq2_{model.replace('.', '_')}_gate_on")
        off = results.get(f"rq2_{model.replace('.', '_')}_gate_off")
        if on:
            on_str = f"{on['accepts']}/{on['n']} ({on['accept_rate']}%)"
        else:
            on_str = "(not run)"
        if off:
            off_str = f"{off['false_accepts']}/{off['n']} ({off['false_accept_rate']}%)"
        else:
            off_str = "(not run)"
        print(f"{model:20s} {on_str:>18s} {off_str:>24s}")
    print(f"{'='*70}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest_subset20.json")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS),
                    help="Comma-separated model list")
    ap.add_argument("--gates", default=",".join(GATE_STATES),
                    help="Comma-separated gate states (gate_on,gate_off)")
    ap.add_argument("--check-models", action="store_true",
                    help="Probe each model before running")
    ap.add_argument("--skip-flow1-for-gate-off", action="store_true",
                    help="Reuse Flow-1 invariants from gate-ON for gate-OFF runs")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    gates = [g.strip() for g in args.gates.split(",") if g.strip()]

    if args.check_models:
        available = []
        for m in models:
            print(f"Checking model {m}...", end=" ", flush=True)
            if check_model_available(m):
                print("OK")
                available.append(m)
            else:
                print("UNAVAILABLE — skipping")
        models = available
        if not models:
            print("ERROR: no models available"); sys.exit(1)

    all_results = {}
    for model in models:
        for gate in gates:
            skip_f1 = (args.skip_flow1_for_gate_off and gate == "gate_off")
            tag = run_cell(args.manifest, model, gate, skip_flow1=skip_f1)
            res = read_cell_results(tag)
            all_results[tag] = res

    print_rq2_table(models, all_results)

    out_path = os.path.join(REPO_ROOT, "results", "rq2_results.json")
    serializable = {}
    for k, v in all_results.items():
        if v:
            serializable[k] = {key: val for key, val in v.items()
                               if key != "per_contract"}
    with open(out_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nSaved results to {out_path}")


if __name__ == "__main__":
    main()
