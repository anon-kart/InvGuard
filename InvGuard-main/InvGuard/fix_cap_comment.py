#!/usr/bin/env python3
"""
fix_cap_comment.py  —  remove the Python '#' comment that leaked into Solidity
==============================================================================
The reentrancy attacker fails to COMPILE because the amount-cap line I injected
carried a Python-style '#' comment that ended up inside the generated Solidity:

  reentryAmt = reentryAmt / 4;  # [INVGUARD_TEMPLATES_PATCH] # [INVGUARD_SEEDING_PATCH] cap
                                ^ '#' is not valid Solidity -> Error(8936) Invalid token

This rewrites both injected cap lines to clean Solidity (no '#', the cap stays
/4). Run from the InvGuard/ directory:
  python fix_cap_comment.py
Backs up flow_2_files/agent.py -> agent.py.bak_capfix. Safe to re-run.
"""
import os, re, shutil, sys

REPO = os.path.dirname(os.path.abspath(__file__))
AG = os.path.join(REPO, "flow_2_files", "agent.py")


def main():
    if not os.path.isfile(AG):
        sys.exit(f"Cannot find {AG}. Run from the InvGuard/ directory.")
    src = open(AG, encoding="utf-8").read()
    orig = src

    # The two injected lines live inside f-strings / plain strings that build the
    # attacker Solidity. The leaked '#' is INSIDE the Solidity string literal.
    # Replace any 'reentryAmt = reentryAmt / N;  # ...<EOL-in-string>' so the
    # emitted Solidity line ends cleanly at the semicolon + \n.

    # Direct-balance branch (f-string):  f'        reentryAmt = reentryAmt / 4;  # ... \n'
    src = re.sub(
        r"reentryAmt = reentryAmt / \d+;\s*#[^\\']*\\n",
        r"reentryAmt = reentryAmt / 4;\\n",
        src,
    )
    # Bare-uint branch (plain string):  "        reentryAmt = reentryAmt / 4;\n"  # [..]
    # Here the '#' is a real PYTHON comment AFTER the string literal — that one is
    # harmless (not in Solidity). But normalize the divisor to /4 just in case the
    # leaked form differs.
    src = re.sub(
        r'"\s*reentryAmt = reentryAmt / \d+;\\n"',
        r'"        reentryAmt = reentryAmt / 4;\\n"',
        src,
    )

    if src == orig:
        print("No matching cap lines found. Inspect manually around "
              "'reentryAmt = reentryAmt /' in flow_2_files/agent.py.")
        # Show the offending lines to help.
        for i, ln in enumerate(orig.splitlines(), 1):
            if "reentryAmt = reentryAmt /" in ln:
                print(f"  line {i}: {ln.strip()}")
        return

    shutil.copy2(AG, AG + ".bak_capfix")
    open(AG, "w", encoding="utf-8").write(src)
    print(f"[capfix] patched. backup at {AG}.bak_capfix")
    # Verify no '#' remains on a reentryAmt cap line that goes into Solidity.
    bad = [ln for ln in src.splitlines()
           if "reentryAmt = reentryAmt /" in ln and "#" in ln and "\\n'" in ln]
    if bad:
        print("!! still found a '#' on a Solidity cap line:")
        for b in bad:
            print("   ", b.strip())
    else:
        print("[capfix] no '#' leaks remain on Solidity cap lines. Good.")
    print("\nVerify it compiles by re-running the reentrancy pair:")
    print("  python run_batch.py --manifest manifest_bench10.json --tag bench10_p3 \\")
    print("     --only bench_re_etherbank_withdraw,bench_re_rewardvault_redeem")
    print("  python reclassify.py --tag bench10_p3")


if __name__ == "__main__":
    main()
