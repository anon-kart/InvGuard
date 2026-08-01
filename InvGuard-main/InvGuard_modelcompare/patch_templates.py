#!/usr/bin/env python3
"""
patch_templates.py  —  fix exploit-template firing on the bench10 set
=====================================================================
Diagnosis from the bench10 run (6 contracts stuck at flow2_no_impactful_exploit):

  * The template fallback chain ALWAYS tries T1 (reentrancy) first, regardless of
    the contract's real class. On non-reentrancy contracts T1 reverts or no-ops,
    and the chain often fails to reach the correct template.
  * T5 (tx.origin) only recognized owner vars named owner/admin/governance, so a
    contract using `holder` (guardedwallet) never matched -> fell to T1.
  * T3 (unchecked return) required a BARE `.send(`; `bool ok = x.send(); ok;`
    (payoutledger) looked "checked" and was skipped, though `ok` is never required.
  * T1's reentrancy attacker withdraws its full balance each re-entry; the victim
    contract's post-call `balance -= amount` then underflows across nested calls
    and reverts the whole tx (etherbank, rewardvault).

This patch makes 4 surgical changes to flow_2_files/agent.py:

  (1) CLASS-DIRECTED CHAIN: order _template_candidates so the template matching
      INVGUARD_VULN_CLASS is tried FIRST. (real capability, not a hack)
  (2) T5 owner detection: also accept holder/keeper/manager/operator/creator and
      "any address state var assigned in the constructor".
  (3) T3 detection: also fire when send()'s result is assigned to a local that is
      never passed to require()/revert (silent check = still unchecked).
  (4) T1 amount cap: reentryAmt uses balance/(maxReentry+1) so nested decrements
      sum to <= the attacker's deposit and never underflow; the stale-balance
      reentry still drains victim funds -> excess_drain > 0.

Backs up agent.py -> agent.py.bak_templates. Safe to re-run.
Run from the InvGuard/ directory:
  python patch_templates.py
"""
import os, re, shutil, sys

REPO = os.path.dirname(os.path.abspath(__file__))
F2 = os.path.join(REPO, "flow_2_files", "agent.py")
MARK = "# [INVGUARD_TEMPLATES_PATCH]"


def patch():
    src = open(F2, encoding="utf-8").read()
    if MARK in src:
        print("[templates] already patched, skipping.")
        return
    orig = src

    # ---- (1) class-directed chain ordering ---------------------------------
    chain_anchor = """        _template_candidates = [
            _make_reentrancy_template_attack(contract_src, TARGET_FUNCTION),
            _make_access_control_template_attack(contract_src),
            _make_unchecked_return_template_attack(contract_src, TARGET_FUNCTION),
            _make_overflow_template_attack(contract_src, TARGET_FUNCTION),
            _make_txorigin_template_attack(contract_src),
        ]"""
    chain_new = """        _tpl_by_class = {  """ + MARK + """
            "reentrancy":       _make_reentrancy_template_attack(contract_src, TARGET_FUNCTION),
            "access_control":   _make_access_control_template_attack(contract_src),
            "unchecked_call":   _make_unchecked_return_template_attack(contract_src, TARGET_FUNCTION),
            "unchecked_return": _make_unchecked_return_template_attack(contract_src, TARGET_FUNCTION),
            "integer_overflow": _make_overflow_template_attack(contract_src, TARGET_FUNCTION),
            "tx_origin":        _make_txorigin_template_attack(contract_src),
        }
        import os as _os_tc
        _decl_class = _os_tc.environ.get("INVGUARD_VULN_CLASS", "").strip()
        _all = [
            _make_reentrancy_template_attack(contract_src, TARGET_FUNCTION),
            _make_access_control_template_attack(contract_src),
            _make_unchecked_return_template_attack(contract_src, TARGET_FUNCTION),
            _make_overflow_template_attack(contract_src, TARGET_FUNCTION),
            _make_txorigin_template_attack(contract_src),
        ]
        _preferred = _tpl_by_class.get(_decl_class)
        if _preferred is not None:
            _template_candidates = [_preferred] + [t for t in _all if t is not _preferred]
        else:
            _template_candidates = _all"""
    if chain_anchor not in src:
        print("!! (1) chain anchor not found — skipping chain reorder.")
    else:
        src = src.replace(chain_anchor, chain_new, 1)

    # ---- (2) T5 owner var detection ----------------------------------------
    t5_anchor = '''    owner_var = None
    for candidate in ["owner", "admin", "governance"]:
        if re.search(rf"address\\s+(?:public\\s+)?{candidate}\\b", clean):'''
    t5_new = '''    owner_var = None
    for candidate in ["owner", "admin", "governance", "holder", "keeper",
                      "manager", "operator", "creator", "controller"]:
        if re.search(rf"address\\s+(?:public\\s+)?{candidate}\\b", clean):'''
    if t5_anchor in src:
        src = src.replace(t5_anchor, t5_new, 1)
    else:
        print("!! (2) T5 owner anchor not found — skipping (check var list manually).")

    # ---- (3) T3 unchecked-send detection -----------------------------------
    t3_anchor = '''    # Look for bare .send( call (not assigned to a bool variable)
    if not re.search(r"[^=\\w]\\.send\\(|^\\s*payable[^=\\n]*\\.send\\(", clean, re.M):
        return None'''
    t3_new = '''    # Look for an UNCHECKED .send(): either a bare call, OR a result assigned to a
    # local that is never passed to require()/revert (a silent no-op check).
    _bare = re.search(r"[^=\\w]\\.send\\(|^\\s*payable[^=\\n]*\\.send\\(", clean, re.M)
    _assigned = re.search(r"\\bbool\\s+(\\w+)\\s*=\\s*[^;]*\\.send\\(", clean)
    _silent = False
    if _assigned:
        _v = _assigned.group(1)
        # If that bool var is never required/reverted on, the check is silent.
        if not re.search(rf"require\\s*\\(\\s*{_v}\\b", clean) and \\
           not re.search(rf"if\\s*\\(\\s*!?\\s*{_v}\\b[^)]*\\)\\s*(revert|{{[^}}]*revert)", clean):
            _silent = True
    if not _bare and not _silent:
        return None'''
    if t3_anchor in src:
        src = src.replace(t3_anchor, t3_new, 1)
    else:
        print("!! (3) T3 anchor not found — skipping (check send detection manually).")

    # ---- (4) T1 reentry amount cap (prevent self-underflow revert) ---------
    # Direct-balance branch: cap to balance/(maxReentry+1).
    t1_direct = '''        if (_bok && _bd.length >= 32) {{ reentryAmt = abi.decode(_bd, (uint256)); }}\\n'
            f'        if (reentryAmt == 0) {{ reentryAmt = (msg.value * 7400) / 10000; }}\''''
    t1_direct_new = '''        if (_bok && _bd.length >= 32) {{ reentryAmt = abi.decode(_bd, (uint256)); }}\\n'
            f'        if (reentryAmt == 0) {{ reentryAmt = (msg.value * 7400) / 10000; }}\\n'
            f'        reentryAmt = reentryAmt / 3;  ''' + MARK + ''' cap so nested decrements do not underflow\\n'
            f'        if (reentryAmt == 0) {{ reentryAmt = 1; }}\''''
    if t1_direct in src:
        src = src.replace(t1_direct, t1_direct_new, 1)
    else:
        print("!! (4a) T1 direct-balance amount anchor not found — skipping.")

    # Bare-uint branch: same cap.
    t1_uint = '''            "        reentryAmt = (msg.value * 7400) / 10000;\\n"
            \'        require(reentryAmt > 0, "amount too small");\''''
    t1_uint_new = '''            "        reentryAmt = (msg.value * 7400) / 10000;\\n"
            "        reentryAmt = reentryAmt / 3;\\n"  ''' + MARK + '''
            \'        require(reentryAmt > 0, "amount too small");\''''
    if t1_uint in src:
        src = src.replace(t1_uint, t1_uint_new, 1)
    else:
        print("!! (4b) T1 bare-uint amount anchor not found — skipping.")

    if src == orig:
        print("!! no changes applied — all anchors missed. Inspect agent.py.")
        return
    shutil.copy2(F2, F2 + ".bak_templates")
    open(F2, "w", encoding="utf-8").write(src)
    print(f"[templates] patched. backup at {F2}.bak_templates")
    print("Applied: (1) class-directed chain, (2) T5 owner vars, "
          "(3) T3 silent-send, (4) T1 amount cap.")


if __name__ == "__main__":
    if not os.path.isfile(F2):
        sys.exit(f"Cannot find {F2}. Run from the InvGuard/ directory.")
    patch()
    print("\nRe-run just the 6 stuck contracts to verify:")
    print('  python run_batch.py --manifest manifest_bench10.json --tag bench10 \\')
    print('     --only bench_re_etherbank_withdraw,bench_re_rewardvault_redeem,'
          'bench_ur_payoutledger_payout,bench_of_tokensale_buy,'
          'bench_of_bonusvault_addBonus,bench_to_guardedwallet_send')
    print('  python reclassify.py --tag bench10')
