#!/usr/bin/env python3
"""
patch_skip_gate.py — Wire INVGUARD_SKIP_GATE into flow_2_files/agent.py
=======================================================================
Two edits:
  1. Add SKIP_GATE env-var read near the feedback-loop controls
  2. In the patch loop, when SKIP_GATE=1:
     - still run validate_patch_non_llm (to record what gate WOULD have said)
     - override ok=True so the first patch is always accepted
     - log the real gate verdict for scoring

USAGE:
  cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"
  python patch_skip_gate.py

Idempotent: running twice is safe (checks before patching).
"""
import os, re, sys

AGENT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "flow_2_files", "agent.py"
)

def patch():
    if not os.path.isfile(AGENT_PATH):
        print(f"ERROR: {AGENT_PATH} not found"); sys.exit(1)

    with open(AGENT_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    changed = False

    # ── EDIT 1: add SKIP_GATE constant after MAX_PATCH_ROUNDS ──
    marker1 = 'MAX_PATCH_ROUNDS = 3  # bounded, reviewer-friendly'
    skip_gate_line = (
        '\n# RQ2 ablation: skip the non-LLM gate, auto-accept first patch.\n'
        'SKIP_GATE = os.environ.get("INVGUARD_SKIP_GATE", "0") == "1"\n'
    )
    if 'SKIP_GATE' not in src:
        if marker1 not in src:
            print("ERROR: cannot find MAX_PATCH_ROUNDS marker"); sys.exit(1)
        src = src.replace(marker1, marker1 + skip_gate_line)
        changed = True
        print("[patch 1/2] Added SKIP_GATE env-var read")
    else:
        print("[patch 1/2] SKIP_GATE already present, skipping")

    # ── EDIT 2: after validate_patch_non_llm call, insert gate-skip logic ──
    old_block = (
        '        validation = validate_patch_non_llm(\n'
        '            repo_root=REPO_ROOT,\n'
        '            original_contract_src=contract_src,\n'
        '            patched_contract_src=fixed_contract,\n'
        '            invariants_path=invariants_path_for_validator,\n'
        '            accepted_attacks=accepted_attacks,\n'
        '            target_function=TARGET_FUNCTION,\n'
        '            attack_id=_accepted_id,\n'
        '        )\n'
        '\n'
        '        val_dir = os.path.join(BASE_EXECUTION_DIR, "patch_validation")\n'
        '        os.makedirs(val_dir, exist_ok=True)\n'
        '        with open(os.path.join(val_dir, "validation_report.json"), "w", encoding="utf-8") as f:\n'
        '            json.dump(validation, f, indent=2)\n'
        '\n'
        '        if validation.get("ok", False):\n'
        '            logging.info("✅ Patch accepted by non-LLM validation gate.")\n'
        '            break'
    )

    new_block = (
        '        validation = validate_patch_non_llm(\n'
        '            repo_root=REPO_ROOT,\n'
        '            original_contract_src=contract_src,\n'
        '            patched_contract_src=fixed_contract,\n'
        '            invariants_path=invariants_path_for_validator,\n'
        '            accepted_attacks=accepted_attacks,\n'
        '            target_function=TARGET_FUNCTION,\n'
        '            attack_id=_accepted_id,\n'
        '        )\n'
        '\n'
        '        if SKIP_GATE:\n'
        '            validation["gate_skipped"] = True\n'
        '            validation["gate_would_have_accepted"] = bool(validation.get("ok", False))\n'
        '            validation["ok"] = True\n'
        '\n'
        '        val_dir = os.path.join(BASE_EXECUTION_DIR, "patch_validation")\n'
        '        os.makedirs(val_dir, exist_ok=True)\n'
        '        with open(os.path.join(val_dir, "validation_report.json"), "w", encoding="utf-8") as f:\n'
        '            json.dump(validation, f, indent=2)\n'
        '\n'
        '        if validation.get("ok", False):\n'
        '            if SKIP_GATE:\n'
        '                logging.info(\n'
        '                    "gate-OFF: patch auto-accepted. "\n'
        '                    f"Gate would have {\'ACCEPTED\' if validation[\'gate_would_have_accepted\'] else \'REJECTED\'}."\n'
        '                )\n'
        '            else:\n'
        '                logging.info("Patch accepted by non-LLM validation gate.")\n'
        '            break'
    )

    if 'gate_skipped' not in src:
        if old_block not in src:
            print("ERROR: cannot find gate-call block to patch")
            print("       (agent.py may have been modified since expected version)")
            sys.exit(1)
        src = src.replace(old_block, new_block, 1)
        changed = True
        print("[patch 2/2] Inserted SKIP_GATE logic in patch loop")
    else:
        print("[patch 2/2] gate_skipped logic already present, skipping")

    if changed:
        with open(AGENT_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"\nDone. Patched {AGENT_PATH}")
    else:
        print("\nNothing to patch (already applied).")


if __name__ == "__main__":
    patch()
