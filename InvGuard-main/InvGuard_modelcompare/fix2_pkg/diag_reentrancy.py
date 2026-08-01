#!/usr/bin/env python3
"""
diag_reentrancy.py  —  dump the exact forge revert trace for the T1 attacker
============================================================================
The reentrancy contracts still fail with run_ok=False / entrypoint_ok=0 (the
forge test reverts) even after the amount cap. To fix it I need the ACTUAL
revert reason, not a guess. This re-runs the saved attacker project under
`forge test -vvvv` and prints the call trace + revert string.

USAGE (after a bench10 run that produced the A1 project dir):
  python diag_reentrancy.py --tag bench10_p1 --stem bench_re_etherbank_withdraw

It finds the saved A1/T1 project under
results/<tag>/<stem>/flow2_outputs/exploit_executor/ and runs forge -vvvv there.
"""
import argparse, glob, os, subprocess, sys

REPO = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--stem", required=True)
    args = ap.parse_args()

    base = os.path.join(REPO, "results", args.tag, args.stem,
                        "flow2_outputs", "exploit_executor")
    if not os.path.isdir(base):
        sys.exit(f"No executor dir at {base}")

    # Prefer the T1 template project; fall back to A1.
    cand = []
    for sub in ("T1", "A1", "A2", "A3"):
        d = os.path.join(base, sub)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "foundry.toml")):
            cand.append(d)
    if not cand:
        # any dir with a foundry.toml
        cand = [os.path.dirname(p) for p in
                glob.glob(os.path.join(base, "*", "foundry.toml"))]
    if not cand:
        sys.exit(f"No foundry project found under {base}")

    proj = cand[0]
    forge = subprocess.run(["bash", "-lc", "command -v forge"],
                           capture_output=True, text=True).stdout.strip()
    if not forge:
        sys.exit("forge not on PATH")

    print(f"=== forge test -vvvv in {proj} ===\n")
    p = subprocess.run([forge, "test", "-vvvv"], cwd=proj,
                       capture_output=True, text=True, timeout=300)
    out = (p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or "")
    # Print the trace around the revert.
    lines = out.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if "Traces:" in ln or "test_run_attack" in ln:
            start = i
            break
    print("\n".join(lines[start:start + 120]))


if __name__ == "__main__":
    main()
