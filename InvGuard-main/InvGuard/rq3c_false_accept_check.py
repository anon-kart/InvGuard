#!/usr/bin/env python3
"""
rq3c_false_accept_check.py — RQ3(c): Independent false-accept verification
============================================================================
For every gate-accepted patch from RQ2, this script:
  1. Copies the patched contract into the sb-heists dataset directory
  2. Runs the sb-heists reference exploit (Hardhat test) against it
  3. If the exploit still succeeds → FALSE ACCEPT (the gate was wrong)
  4. If the exploit fails → CONFIRMED FIX

This is the independent verification arm — it does NOT use InvGuard's
own gate to judge (avoids circularity).

USAGE:
  cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"
  python rq3c_false_accept_check.py --tag rq2_gpt-4o-mini_gate_on
  python rq3c_false_accept_check.py --all-tags

The script generates and runs Hardhat commands. Requires:
  - cd to sb-heists/smartbugs-curated/0.4.x  (or set --sb-heists-root)
  - npx hardhat available in that directory
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

STEM_TO_CONTRACT_PATH = {
    "acces_FibonacciBalance": ("access_control", "FibonacciBalance.sol", "FibonacciBalance"),
    "acces_multiowned_vulnerable": ("access_control", "multiowned_vulnerable.sol", "multiowned"),
    "acces_parity_wallet_bug_2": ("access_control", "parity_wallet_bug_2.sol", "WalletLibrary"),
    "acces_unprotected0": ("access_control", "unprotected0.sol", "Unprotected"),
    "integ_BECToken": ("arithmetic", "BECToken.sol", "BecToken"),
    "integ_overflow_single_tx": ("arithmetic", "overflow_single_tx.sol", "IntegerOverflowSingleTransaction"),
    "bad_r_blackjack": ("bad_randomness", "blackjack.sol", "BlackJack"),
    "bad_r_etheraffle": ("bad_randomness", "etheraffle.sol", "Etheraffle"),
    "bad_r_guess_the_random_number": ("bad_randomness", "guess_the_random_number.sol", "GuessTheRandomNumber"),
    "bad_r_old_blockhash": ("bad_randomness", "old_blockhash.sol", "OldBlockhash"),
    "denia_auction": ("denial_of_service", "auction.sol", "DosAuction"),
    "denia_dos_address": ("denial_of_service", "dos_address.sol", "DosAuction"),
    "denia_dos_number": ("denial_of_service", "dos_number.sol", "DosNumber"),
    "denia_dos_simple": ("denial_of_service", "dos_simple.sol", "DosSimple"),
    "reent_0x4e73b32ed6c35f570686b89848e5f39f20ecc106": ("reentrancy", "0x4e73b32ed6c35f570686b89848e5f39f20ecc106.sol", "PERSONAL_BANK"),
    "reent_modifier_reentrancy": ("reentrancy", "modifier_reentrancy.sol", "ModifierEntrancy"),
    "reent_reentrancy_bonus": ("reentrancy", "reentrancy_bonus.sol", "Bonus"),
    "unche_0x07f7ecb66d788ab01dc93b9b71a88401de7d0f2e": ("unchecked_low_level_calls", "0x07f7ecb66d788ab01dc93b9b71a88401de7d0f2e.sol", "PoCGame"),
    "unche_0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839": ("unchecked_low_level_calls", "0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol", "TokenBank"),
    "unche_0x89c1b3807d4c67df034fffb62f3509561218d30b": ("unchecked_low_level_calls", "0x89c1b3807d4c67df034fffb62f3509561218d30b.sol", "PinCodeEtherStorage"),
}

STEM_TO_TEST = {
    "acces_FibonacciBalance": "test/access_control/FibonacciBalance_test.js",
    "acces_multiowned_vulnerable": "test/access_control/multiowned_vulnerable_test.js",
    "acces_parity_wallet_bug_2": "test/access_control/parity_wallet_bug_2_test.js",
    "acces_unprotected0": "test/access_control/unprotected0_test.js",
    "integ_BECToken": "test/arithmetic/BECToken_test.js",
    "integ_overflow_single_tx": "test/arithmetic/overflow_single_tx_test.js",
    "bad_r_blackjack": "test/bad_randomness/blackjack_test.js",
    "bad_r_etheraffle": "test/bad_randomness/etheraffle_test.js",
    "bad_r_guess_the_random_number": "test/bad_randomness/guess_the_random_number_test.js",
    "bad_r_old_blockhash": "test/bad_randomness/old_blockhash_test.js",
    "denia_auction": "test/denial_of_service/auction_test.js",
    "denia_dos_address": "test/denial_of_service/dos_address_test.js",
    "denia_dos_number": "test/denial_of_service/dos_number_test.js",
    "denia_dos_simple": "test/denial_of_service/dos_simple_test.js",
    "reent_0x4e73b32ed6c35f570686b89848e5f39f20ecc106": "test/reentrancy/0x4e73b32ed6c35f570686b89848e5f39f20ecc106_test.js",
    "reent_modifier_reentrancy": "test/reentrancy/modifier_reentrancy_test.js",
    "reent_reentrancy_bonus": "test/reentrancy/reentrancy_bonus_test.js",
    "unche_0x07f7ecb66d788ab01dc93b9b71a88401de7d0f2e": "test/unchecked_low_level_calls/0x07f7ecb66d788ab01dc93b9b71a88401de7d0f2e_test.js",
    "unche_0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839": "test/unchecked_low_level_calls/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839_test.js",
    "unche_0x89c1b3807d4c67df034fffb62f3509561218d30b": "test/unchecked_low_level_calls/0x89c1b3807d4c67df034fffb62f3509561218d30b_test.js",
}


def find_patched_contract(stem, tag):
    stem_dir = os.path.join(REPO_ROOT, "results", tag, stem)
    patch_path = os.path.join(stem_dir, "flow2_outputs", "patch_validation",
                              "patched_contract.sol")
    if os.path.isfile(patch_path):
        return patch_path
    return None


def check_one(stem, tag, sb_root, dry_run=False):
    info = STEM_TO_CONTRACT_PATH.get(stem)
    test_rel = STEM_TO_TEST.get(stem)
    if not info or not test_rel:
        return {"stem": stem, "status": "no_mapping"}

    vuln_class, sol_file, main_contract = info
    patch_path = find_patched_contract(stem, tag)
    if not patch_path:
        return {"stem": stem, "status": "no_patch_file"}

    dataset_target = os.path.join(sb_root, "contracts", "dataset",
                                  vuln_class, sol_file)
    backup_path = dataset_target + ".orig"
    test_path = os.path.join(sb_root, test_rel)

    if not os.path.isfile(test_path):
        return {"stem": stem, "status": "no_test_file", "test": test_rel}

    if dry_run:
        return {"stem": stem, "status": "dry_run",
                "patch": patch_path, "target": dataset_target, "test": test_rel}

    if not os.path.isfile(backup_path):
        shutil.copy2(dataset_target, backup_path)

    shutil.copy2(patch_path, dataset_target)

    try:
        result = subprocess.run(
            ["npx", "hardhat", "test", test_path],
            cwd=sb_root,
            capture_output=True, text=True, timeout=120,
        )
        exploit_blocked = result.returncode != 0
        return {
            "stem": stem,
            "status": "confirmed_fix" if exploit_blocked else "FALSE_ACCEPT",
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"stem": stem, "status": "timeout"}
    finally:
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, dataset_target)
            os.remove(backup_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="rq2_gpt-4o-mini_gate_on")
    ap.add_argument("--sb-heists-root",
                    default="/home/kartik/Downloads/sb-heists/smartbugs-curated/0.4.x")
    ap.add_argument("--all-tags", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be done without running Hardhat")
    args = ap.parse_args()

    if args.all_tags:
        tags = [
            "rq2_gpt-4o-mini_gate_on",
            "rq2_gpt-5-mini_gate_on",
            "rq2_gpt-5_5_gate_on",
        ]
    else:
        tags = [args.tag]

    for tag in tags:
        summary_path = os.path.join(REPO_ROOT, "results", tag, "_batch_summary.json")
        if not os.path.isfile(summary_path):
            print(f"No results for {tag}")
            continue

        data = json.load(open(summary_path))
        accepted = [r for r in data if r.get("gate", {}).get("accepted")]

        print(f"\nRQ3(c) — False-Accept Check: {tag}")
        print(f"  Gate-accepted patches: {len(accepted)}/{len(data)}")
        print(f"{'='*65}")

        confirmed = 0
        false_accepts = 0
        errors = 0

        for r in accepted:
            stem = r["stem"]
            res = check_one(stem, tag, args.sb_heists_root, dry_run=args.dry_run)
            status = res["status"]

            if status == "confirmed_fix":
                confirmed += 1
                print(f"  CONFIRMED  {stem}")
            elif status == "FALSE_ACCEPT":
                false_accepts += 1
                print(f"  FALSE_ACCEPT  {stem}")
                print(f"    stdout: {res.get('stdout_tail','')[:200]}")
            elif status == "dry_run":
                print(f"  [dry-run]  {stem}")
                print(f"    patch:  {res['patch']}")
                print(f"    target: {res['target']}")
                print(f"    test:   {res['test']}")
            else:
                errors += 1
                print(f"  {status:14s}  {stem}")

        print(f"\n  Summary: {confirmed} confirmed, {false_accepts} false-accept, {errors} error/skip")
        print(f"  False-accept rate: {false_accepts}/{confirmed+false_accepts}"
              f" ({100*false_accepts/(confirmed+false_accepts):.1f}%)"
              if (confirmed+false_accepts) > 0 else "  No patches to check")
        print()

    out_path = os.path.join(REPO_ROOT, "results", "rq3c_results.json")
    print(f"Done. Run without --dry-run to execute Hardhat checks.")


if __name__ == "__main__":
    main()
