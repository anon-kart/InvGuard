#!/usr/bin/env python3
"""
patch_flow1_targetfn.py  —  make Flow-1 verify the TARGET_FUNCTION
==================================================================
ROOT CAUSE of the 0/22 run:
  flow_1_files/agent.py is hard-wired to run its deterministic Z3 checks ONLY on
  functions literally named "deposit" and "withdraw". For contracts whose target
  function is bid / claimThrone / collectAllFees / distributeDividend / migrate /
  Collect / ..., Flow-1 checked deposit+withdraw (which don't exist), produced
  ZERO verified invariants, and Flow-2 then correctly refused ("No verified-useful
  invariants for <fn>").

THE FIX (surgical, reversible):
  Add the env-provided TARGET_FUNCTION to Flow-1's run_queue, fed with the full
  sanitized invariant set, so Flow-1 emits invariants.<TARGET_FUNCTION>.VU/VM.txt
  — exactly the files Flow-2 looks for. deposit/withdraw still run when present,
  so bank/vault contracts that already worked keep working.

This script edits, in place, with a .bak_targetfn backup:
  1. flow_1_files/agent.py   — inject TARGET_FUNCTION into the run queue
  2. run_batch.py            — report a precise gate reason instead of "no_report"

Run ONCE from the InvGuard/ directory:
  python patch_flow1_targetfn.py
Re-running is safe: it detects the marker and skips if already applied.
"""
import os, re, shutil, sys

REPO = os.path.dirname(os.path.abspath(__file__))
F1 = os.path.join(REPO, "flow_1_files", "agent.py")
RB = os.path.join(REPO, "run_batch.py")

MARK = "# [INVGUARD_TARGETFN_PATCH]"


def patch_flow1():
    src = open(F1, encoding="utf-8").read()
    if MARK in src:
        print("[flow1] already patched, skipping.")
        return
    # Anchor: the run_queue construction block.
    anchor = '    run_queue = []\n'
    if anchor not in src:
        print("!! [flow1] could not find run_queue anchor. No change made.")
        print("   Open flow_1_files/agent.py, find 'run_queue = []' (~line 2350),")
        print("   and apply the manual block printed below.")
        print(MANUAL_BLOCK)
        return

    inject = (
        anchor +
        f"    {MARK} inject the env TARGET_FUNCTION so Flow-1 verifies the\n"
        "    # actual function Flow-2 will repair (not just deposit/withdraw).\n"
        "    import os as _os_tf\n"
        "    _target_fn = _os_tf.environ.get('TARGET_FUNCTION', '').strip()\n"
        "    if _target_fn and _target_fn not in ('deposit', 'withdraw'):\n"
        "        # Feed the target function the full usable invariant set.\n"
        "        # Neutral + arg-free lines are broadly applicable; if empty,\n"
        "        # fall back to all sanitized lines so the file is non-empty.\n"
        "        _tf_lines = [x for x in all_lines if x.strip()]\n"
        "        if _tf_lines:\n"
        "            _tf_lines = _final_repair_invariant_lines(_tf_lines)\n"
        "            _tf_path = os.path.join(BASE_EXECUTION_DIR,\n"
        "                                    f'invariants.{_target_fn}.filtered.txt')\n"
        "            with open(_tf_path, 'w', encoding='utf-8') as _tf_f:\n"
        "                _tf_f.write('\\n'.join(_tf_lines) + '\\n')\n"
        "            run_queue.append((_target_fn, _tf_path))\n"
    )
    src2 = src.replace(anchor, inject, 1)
    shutil.copy2(F1, F1 + ".bak_targetfn")
    open(F1, "w", encoding="utf-8").write(src2)
    print(f"[flow1] patched. backup at {F1}.bak_targetfn")


def patch_runbatch():
    """Make _read_gate distinguish flow2-no-exploit / flow1-empty / gate-reject."""
    src = open(RB, encoding="utf-8").read()
    if MARK in src:
        print("[run_batch] already patched, skipping.")
        return
    old = '''    out = {"accepted": False, "reason": "no_report", "verdicts": {}}
    if not os.path.isfile(vr):
        return out'''
    new = f'''    out = {{"accepted": False, "reason": "no_report", "verdicts": {{}}}}  {MARK}
    if not os.path.isfile(vr):
        # No validation report: figure out WHY from the flow logs.
        f2log = os.path.join(stem_dir, "flow2.log")
        f1log = os.path.join(stem_dir, "flow1.log")
        txt = ""
        for lp in (f2log, f1log):
            if os.path.isfile(lp):
                txt += open(lp, encoding="utf-8", errors="ignore").read()
        if "No verified-useful invariants" in txt:
            out["reason"] = "flow1_no_verified_invariants"
        elif "no executable impactful exploit" in txt or \\
             "No repair claim is made" in txt:
            out["reason"] = "flow2_no_impactful_exploit"
        elif "Checker failed" in txt or "Z3Checker failed" in txt:
            out["reason"] = "flow1_z3_infra_fail"
        else:
            out["reason"] = "no_report"
        return out'''
    if old not in src:
        print("!! [run_batch] gate block not found (already edited?). Skipping.")
        return
    src2 = src.replace(old, new, 1)
    shutil.copy2(RB, RB + ".bak_targetfn")
    open(RB, "w", encoding="utf-8").write(src2)
    print(f"[run_batch] patched. backup at {RB}.bak_targetfn")


MANUAL_BLOCK = """
--- paste right AFTER the line `run_queue = []` in flow_1_files/agent.py ---
    import os as _os_tf
    _target_fn = _os_tf.environ.get('TARGET_FUNCTION', '').strip()
    if _target_fn and _target_fn not in ('deposit', 'withdraw'):
        _tf_lines = [x for x in all_lines if x.strip()]
        if _tf_lines:
            _tf_lines = _final_repair_invariant_lines(_tf_lines)
            _tf_path = os.path.join(BASE_EXECUTION_DIR,
                                    f'invariants.{_target_fn}.filtered.txt')
            with open(_tf_path, 'w', encoding='utf-8') as _tf_f:
                _tf_f.write('\\n'.join(_tf_lines) + '\\n')
            run_queue.append((_target_fn, _tf_path))
----------------------------------------------------------------------------
"""


if __name__ == "__main__":
    if not os.path.isfile(F1):
        sys.exit(f"Cannot find {F1}. Run this from the InvGuard/ directory.")
    patch_flow1()
    patch_runbatch()
    print("\nDone. Now re-run a SINGLE contract to confirm the fix end-to-end:")
    print('  CONTRACT_FILE=contracts/nssc_auction_bid.sol TARGET_FUNCTION=bid \\\\')
    print("      python flow_1_files/agent.py")
    print("  then check: ls run_outputs/flow1_verified_invariants/invariants.bid.*.txt")
