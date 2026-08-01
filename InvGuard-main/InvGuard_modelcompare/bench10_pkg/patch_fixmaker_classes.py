#!/usr/bin/env python3
"""
patch_fixmaker_classes.py  —  add tx_origin + integer_overflow repair branches
==============================================================================
Your pipeline has T4 (overflow) and T5 (tx.origin) ATTACK templates that confirm
impact, but the class-aware FixMaker has no repair instruction for them, so they
fall through to the CEI default and get gate_rejected. This adds the two missing
branches so all 5 supported classes work end-to-end.

Run ONCE from the InvGuard/ directory:
  python patch_fixmaker_classes.py
Backs up flow_2_files/agent.py -> agent.py.bak_fixclasses. Safe to re-run.
"""
import os, shutil, sys

REPO = os.path.dirname(os.path.abspath(__file__))
F2 = os.path.join(REPO, "flow_2_files", "agent.py")
MARK = "# [INVGUARD_FIXCLASS_PATCH]"

ANCHOR = '''            ).format(fn=TARGET_FUNCTION),
        }.get(_vclass,
              "Apply Checks-Effects-Interactions (move all state updates BEFORE "
              "the external call).")'''

INJECT = '''            ).format(fn=TARGET_FUNCTION),
            "tx_origin": (  ''' + MARK + '''
                "This is a tx.origin AUTHENTICATION bug. {fn}() uses `tx.origin` "
                "for authorization, which a malicious intermediary contract can "
                "exploit by getting the owner to call it. Replace every "
                "`tx.origin == <owner>` authentication check in {fn}() with "
                "`msg.sender == <owner>`. Do not change anything else."
            ).format(fn=TARGET_FUNCTION),
            "integer_overflow": (
                "This is an INTEGER-OVERFLOW/UNDERFLOW bug. {fn}() performs "
                "arithmetic that can wrap around (an unchecked block on 0.8+, or "
                "implicit wrapping on pragma <0.8.0). Remove the unchecked block "
                "so the compiler's built-in checks apply, or on pre-0.8 add an "
                "explicit bound check before writing the result. Preserve "
                "behavior for non-overflowing inputs."
            ).format(fn=TARGET_FUNCTION),
        }.get(_vclass,
              "Apply Checks-Effects-Interactions (move all state updates BEFORE "
              "the external call).")'''


def main():
    if not os.path.isfile(F2):
        sys.exit(f"Cannot find {F2}. Run from the InvGuard/ directory.")
    src = open(F2, encoding="utf-8").read()
    if MARK in src:
        print("[fixmaker] already patched, skipping.")
        return
    if ANCHOR not in src:
        sys.exit("!! anchor not found — the dict may have been edited. "
                 "Apply ADD_FIXMAKER_BRANCHES.md by hand.")
    shutil.copy2(F2, F2 + ".bak_fixclasses")
    open(F2, "w", encoding="utf-8").write(src.replace(ANCHOR, INJECT, 1))
    print(f"[fixmaker] patched. backup at {F2}.bak_fixclasses")
    print("Now tx_origin and integer_overflow route to real repair instructions.")


if __name__ == "__main__":
    main()
