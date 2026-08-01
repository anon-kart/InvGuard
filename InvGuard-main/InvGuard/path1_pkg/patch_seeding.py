#!/usr/bin/env python3
"""
patch_seeding.py  —  make victim-seeding work for any contract (Path 1)
=======================================================================
Root cause of the remaining harness reverts: the exploit harness seeds the
victim with 10 ETH ONLY through a fixed set of payable entry functions
(addCollateral/deposit/Deposit/Collect). Contracts whose entry is stake(),
fund(address), or which have no payable entry, fall to `transfer(msg.value)`,
which reverts if the contract has no receive()/fallback — so the whole forge
test reverts before the attack even runs.

Fixes (flow_2_files/exploit_executor.py):
  (1) Add stake() and fund(address) to the PriorDepositor seed chain.
  (2) GUARANTEE funds regardless of entry API: after each seeder.seed(...) call,
      add `vm.deal(address(target), address(target).balance + 10 ether);` so the
      victim always holds victim-ETH even when no payable entry exists. vm.deal
      sets balance directly and never reverts.
  (3) Make the seeder's final fallback non-reverting: wrap transfer in a
      low-level call so a missing receive() doesn't abort the harness.

Also re-tunes the T1 reentrancy amount cap in flow_2_files/agent.py from /3 to
/4 (etherbank/rewardvault still self-underflowed at /3 because the victim's
post-call decrement runs maxReentry+1 = 3 times AND the honest baseline consumes
one share; /4 leaves headroom).

Backs up both files (.bak_seeding). Safe to re-run.
Run from the InvGuard/ directory:
  python patch_seeding.py
"""
import os, shutil, sys

REPO = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(REPO, "flow_2_files", "exploit_executor.py")
AG = os.path.join(REPO, "flow_2_files", "agent.py")
MARK = "# [INVGUARD_SEEDING_PATCH]"
MARK_SOL = "// [INVGUARD_SEEDING_PATCH]"


def patch_executor():
    src = open(EX, encoding="utf-8").read()
    if MARK in src or MARK_SOL in src:
        print("[seeding] executor already patched, skipping.")
        return
    orig = src

    # (1) extend the seed chain: add stake() and fund(address) before the final
    #     transfer fallback.
    seed_anchor = '''        (bool ok5,) = payable(target).call{{value: msg.value}}(abi.encodeWithSignature("Collect()"));
        if (ok5) return;
        // Final fallback: raw ETH transfer
        payable(target).transfer(msg.value);'''
    seed_new = '''        (bool ok5,) = payable(target).call{{value: msg.value}}(abi.encodeWithSignature("Collect()"));
        if (ok5) return;
        ''' + MARK_SOL + '''
        (bool ok6,) = payable(target).call{{value: msg.value}}(abi.encodeWithSignature("stake()"));
        if (ok6) return;
        (bool ok7,) = payable(target).call{{value: msg.value}}(abi.encodeWithSignature("fund(address)", address(this)));
        if (ok7) return;
        // Final fallback: non-reverting raw send (missing receive() must not abort harness)
        (bool ok8,) = payable(target).call{{value: msg.value}}("");
        ok8;'''
    if seed_anchor in src:
        src = src.replace(seed_anchor, seed_new, 1)
    else:
        print("!! (1) seed-chain anchor not found — skipping chain extension.")

    # (2) guarantee victim funds after the primary seed call.
    primary = '''        seeder.seed{{value: 10 ether}}(address(target));'''
    primary_new = '''        seeder.seed{{value: 10 ether}}(address(target));
        ''' + MARK_SOL + ''' guarantee victim ETH regardless of entry API
        vm.deal(address(target), address(target).balance + 10 ether);'''
    if primary in src:
        src = src.replace(primary, primary_new, 1)
    else:
        print("!! (2a) primary seed call not found — skipping deal-guarantee.")

    baseline = '''            bseeder.seed{{value: 10 ether}}(address(baseline));'''
    baseline_new = '''            bseeder.seed{{value: 10 ether}}(address(baseline));
            ''' + MARK_SOL + ''' identical guarantee for the honest baseline
            vm.deal(address(baseline), address(baseline).balance + 10 ether);'''
    if baseline in src:
        src = src.replace(baseline, baseline_new, 1)
    else:
        print("!! (2b) baseline seed call not found — skipping deal-guarantee.")

    if src == orig:
        print("!! executor: no changes applied.")
    else:
        shutil.copy2(EX, EX + ".bak_seeding")
        open(EX, "w", encoding="utf-8").write(src)
        print(f"[seeding] executor patched. backup at {EX}.bak_seeding")


def patch_agent_t1cap():
    src = open(AG, encoding="utf-8").read()
    if MARK in src:
        print("[seeding] agent T1-cap already patched, skipping.")
        return
    orig = src
    # /3 -> /4 in both injected cap lines from patch_templates.
    a = "reentryAmt = reentryAmt / 3;  # [INVGUARD_TEMPLATES_PATCH] cap so nested decrements do not underflow"
    a_new = "reentryAmt = reentryAmt / 4;  # [INVGUARD_TEMPLATES_PATCH] " + MARK + " cap"
    if a in src:
        src = src.replace(a, a_new, 1)
    b = '"        reentryAmt = reentryAmt / 3;\\n"  # [INVGUARD_TEMPLATES_PATCH]'
    b_new = '"        reentryAmt = reentryAmt / 4;\\n"  # [INVGUARD_TEMPLATES_PATCH] ' + MARK
    if b in src:
        src = src.replace(b, b_new, 1)
    if src == orig:
        print("!! agent: T1 cap lines not found (did you run patch_templates.py first?).")
    else:
        shutil.copy2(AG, AG + ".bak_seeding")
        open(AG, "w", encoding="utf-8").write(src)
        print(f"[seeding] agent T1-cap retuned /3 -> /4. backup at {AG}.bak_seeding")


if __name__ == "__main__":
    if not os.path.isfile(EX):
        sys.exit(f"Cannot find {EX}. Run from the InvGuard/ directory.")
    patch_executor()
    patch_agent_t1cap()
    print("\nDone. Re-run the reentrancy + reseed-dependent contracts:")
    print("  python run_batch.py --manifest manifest_bench10.json --tag bench10 \\")
    print("     --only bench_re_etherbank_withdraw,bench_re_rewardvault_redeem,"
          "bench_ur_payoutledger_payout")
    print("  python reclassify.py --tag bench10")
