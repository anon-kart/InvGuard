#!/usr/bin/env python3
"""
solidifi_pilot20.py — Select 20 pilot cases from SolidiFI
==========================================================
Scans a local SolidiFI-benchmark clone, catalogs every mutant in the
four InvGuard-supported categories, filters for compilability and
reachability, deduplicates, and selects 20 cases (5 per InvGuard class)
using host-balanced stratified sampling.

Category mapping (SolidiFI → InvGuard):
  Re-entrancy          → reentrancy         (5 cases)
  Overflow-Underflow   → integer_overflow   (5 cases)
  Unhandled-Exceptions → unchecked_call     (3 cases)
  Unchecked-Send       → unchecked_call     (2 cases)
  tx.origin            → tx_origin          (5 cases)

USAGE:
  cd "/home/kartik/Downloads/InvGuard-main (1)/InvGuard-main/InvGuard"

  python solidifi_pilot20.py \
      --solidifi-root ~/Downloads/SolidiFI-benchmark \
      --out solidifi_pilot20.json \
      --seed 2026

  # If solc is not on PATH or you want to skip the compile check:
  python solidifi_pilot20.py \
      --solidifi-root ~/Downloads/SolidiFI-benchmark \
      --out solidifi_pilot20.json \
      --skip-compile

Outputs:
  solidifi_pilot20.json          20 primary cases (run_batch.py format)
  solidifi_pilot20_catalog.csv   full catalog of all scanned mutants
  solidifi_pilot20_funnel.json   filtering funnel counts
"""
import argparse
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

RANDOM_SEED = 2026

# ── Category mapping ────────────────────────────────────────────────
# Keys are directory names that may appear under buggy_contracts/.
# Values are (invguard_class, solidifi_subclass).

CATEGORY_MAP = {
    "Re-entrancy":          ("reentrancy",      "reentrancy"),
    "Reentrancy":           ("reentrancy",      "reentrancy"),
    "reentrancy":           ("reentrancy",      "reentrancy"),
    "Overflow-Underflow":   ("integer_overflow","overflow_underflow"),
    "overflow_underflow":   ("integer_overflow","overflow_underflow"),
    "Integer-Overflow":     ("integer_overflow","overflow_underflow"),
    "Unhandled-Exceptions": ("unchecked_call",  "unhandled_exceptions"),
    "unhandled_exceptions": ("unchecked_call",  "unhandled_exceptions"),
    "Unchecked-Send":       ("unchecked_call",  "unchecked_send"),
    "unchecked_send":       ("unchecked_call",  "unchecked_send"),
    "tx.origin":            ("tx_origin",       "tx_origin"),
    "tx-origin":            ("tx_origin",       "tx_origin"),
    "txorigin":             ("tx_origin",       "tx_origin"),
}

EXCLUDED_DIRS = {
    "Timestamp-Dependency", "timestamp_dependency", "Timestamp",
    "TOD", "tod", "Transaction-Order-Dependence",
    "front_running", "Front-Running", "other", "short_addresses",
    "time_manipulation",
}

# Pilot allocation: 5 per InvGuard class.
# unchecked_call draws from two SolidiFI subcategories.
PILOT_ALLOCATION = {
    "reentrancy":       {"total": 5, "sub": {"reentrancy": 5}},
    "integer_overflow": {"total": 5, "sub": {"overflow_underflow": 5}},
    "unchecked_call":   {"total": 5, "sub": {"unhandled_exceptions": 3,
                                              "unchecked_send": 2}},
    "tx_origin":        {"total": 5, "sub": {"tx_origin": 5}},
}

MAX_PER_HOST = 2


# ── Discovery ────────────────────────────────────────────────────────

def discover(root):
    root = Path(root)
    cases = []

    # Try standard locations for buggy contracts
    buggy_dir = None
    for candidate in [root / "buggy_contracts",
                      root / "dataset",
                      root / "bugs",
                      root]:
        if candidate.is_dir():
            subdirs = [d for d in candidate.iterdir()
                       if d.is_dir() and d.name not in {".", "..", ".git",
                                                         "__pycache__", "results"}]
            if subdirs:
                buggy_dir = candidate
                break

    if not buggy_dir:
        print(f"ERROR: cannot find buggy contract directories under {root}")
        sys.exit(1)

    # Try standard locations for clean host contracts
    clean_dir = None
    for candidate in [root / "contracts",
                      root / "clean_contracts",
                      root / "original_contracts"]:
        if candidate.is_dir():
            clean_dir = candidate
            break

    print(f"  Buggy contracts dir: {buggy_dir}")
    print(f"  Clean contracts dir: {clean_dir or '(not found)'}")
    print()

    for cat_dir in sorted(buggy_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        dirname = cat_dir.name
        if dirname in EXCLUDED_DIRS or dirname.startswith("."):
            continue

        mapping = CATEGORY_MAP.get(dirname)
        if not mapping:
            alt = dirname.replace("-", "_").replace(" ", "_").lower()
            mapping = CATEGORY_MAP.get(alt)
        if not mapping:
            print(f"  [skip] unrecognized directory: {dirname}")
            continue

        invguard_class, solidifi_sub = mapping

        sol_files = sorted(cat_dir.glob("*.sol"))
        if not sol_files:
            # Try one level deeper
            for sub in cat_dir.iterdir():
                if sub.is_dir():
                    sol_files.extend(sorted(sub.glob("*.sol")))

        for sol_file in sol_files:
            host_id = _extract_host_id(sol_file)
            clean_path = _find_clean(clean_dir, host_id)
            cases.append({
                "file": str(sol_file),
                "filename": sol_file.name,
                "dir_name": dirname,
                "invguard_class": invguard_class,
                "solidifi_sub": solidifi_sub,
                "host_id": host_id,
                "clean_contract": str(clean_path) if clean_path else "",
            })

    return cases


def _extract_host_id(path):
    name = path.stem
    # buggy_42 → 42; buggy_42_v2 → 42; contract_7 → 7
    m = re.search(r"(\d+)", name)
    return m.group(1) if m else name


def _find_clean(clean_dir, host_id):
    if not clean_dir or not clean_dir.is_dir():
        return None
    for pattern in [f"{host_id}.sol",
                    f"contract_{host_id}.sol",
                    f"clean_{host_id}.sol"]:
        p = clean_dir / pattern
        if p.is_file():
            return p
    # Fuzzy match
    for f in clean_dir.glob("*.sol"):
        if host_id in f.stem and f.stem.replace(host_id, "").strip("_- ") in (
                "", "clean", "original", "contract"):
            return f
    return None


# ── Parsing and filtering ────────────────────────────────────────────

def parse_sol(path):
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"pragma": None, "contracts": [], "functions": [],
                "source": "", "lines": 0}

    pragma_m = re.search(r"pragma\s+solidity\s+([^;]+);", src)
    contracts = re.findall(r"contract\s+(\w+)", src)
    functions = re.findall(r"function\s+(\w+)\s*\(", src)
    return {
        "pragma": pragma_m.group(1).strip() if pragma_m else None,
        "contracts": contracts,
        "functions": functions,
        "source": src,
        "lines": src.count("\n") + 1,
    }


def is_reachable(parsed):
    src = parsed["source"]
    return bool(re.search(
        r"function\s+\w+\s*\([^)]*\)\s*(public|external)", src
    )) or bool(re.search(
        r"function\s*\(\s*\)\s*(public|external|payable)", src
    ))


def try_compile(path):
    # Method 1: solc on PATH
    for solc in ["solc", os.path.expanduser("~/.solcx/solc-v0.5.12/solc")]:
        try:
            proc = subprocess.run(
                [solc, "--combined-json", "bin", str(path)],
                capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                return True, ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Method 2: py-solc-x
    try:
        import solcx
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"pragma\s+solidity\s+\^?(\d+\.\d+\.\d+)", src)
        ver = m.group(1) if m else "0.5.12"
        try:
            solcx.install_solc(ver)
        except Exception:
            pass
        solcx.compile_source(src, solc_version=ver)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]

    return False, "no compiler available"


def classify_context(case, parsed):
    cls = case["invguard_class"]
    sub = case["solidifi_sub"]
    src = parsed["source"]

    if cls == "reentrancy":
        if re.search(r"\.call\.value\(", src):
            if re.search(r"\b(balance|balances|credit)\b.*-=", src):
                return "state_after_value_call"
            return "value_call"
        if re.search(r"\.send\(", src):
            return "send_before_update"
        return "generic_reentry"

    elif cls == "integer_overflow":
        if re.search(r"\+=", src):
            return "addition_overflow"
        if re.search(r"-=", src):
            return "subtraction_underflow"
        if re.search(r"\*=?[^/]", src):
            return "multiplication"
        return "generic_arithmetic"

    elif cls == "unchecked_call":
        if sub == "unchecked_send":
            if re.search(r"for\s*\(", src):
                return "loop_send"
            return "standalone_send"
        else:
            if re.search(r"\.call\s*[.(]", src):
                return "ignored_call_return"
            if re.search(r"\.send\(", src):
                return "unchecked_send_value"
            return "generic_exception"

    elif cls == "tx_origin":
        if re.search(r"require\s*\(\s*tx\.origin", src):
            return "require_txorigin"
        if re.search(r"tx\.origin\s*==\s*\w*[Oo]wner", src):
            return "owner_check"
        return "generic_txorigin"

    return "unknown"


def dedup_key(case, parsed):
    components = [
        case["invguard_class"],
        case["solidifi_sub"],
        case["host_id"],
    ]
    # Normalize source for fingerprinting
    src = re.sub(r"//[^\n]*", "", parsed["source"])
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"\s+", " ", src).strip()[:2000]
    components.append(src)
    raw = "|".join(components)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Target function heuristic ────────────────────────────────────────

FUNCTION_HINTS = {
    "reentrancy": ["withdraw", "withdrawBalance", "cashout", "CashOut",
                    "Collect", "collect", "redeem", "claim", "refund",
                    "getBalance", "withdrawAll", "withdrawFunds"],
    "integer_overflow": ["transfer", "batchTransfer", "buy", "sell",
                          "mint", "burn", "addBonus", "increaseLockTime",
                          "sendCoin", "approve", "transferFrom"],
    "unchecked_call": ["refund", "refundAll", "send", "payout",
                        "distribute", "release", "pay", "transfer",
                        "withdraw", "execute", "forward"],
    "tx_origin": ["withdraw", "transferTo", "sendTo", "execute",
                   "changeOwner", "setOwner", "transferOwnership",
                   "destroyContract", "kill"],
}

SKIP_FUNCTIONS = {"constructor", "require", "assert", "revert", "emit",
                  "log", "add", "sub", "mul", "div", "mod",
                  "safeMul", "safeDiv", "safeAdd", "safeSub",
                  "Log", "Event"}


def pick_target_function(parsed, vuln_class):
    fns = parsed["functions"]
    if not fns:
        return "fallback"

    hints = FUNCTION_HINTS.get(vuln_class, [])
    for h in hints:
        for f in fns:
            if f.lower() == h.lower():
                return f

    for f in fns:
        if f not in SKIP_FUNCTIONS and not f[0].isupper():
            return f
    for f in fns:
        if f not in SKIP_FUNCTIONS:
            return f
    return fns[0]


# ── Impact policy ────────────────────────────────────────────────────

def impact_policy(vuln_class):
    return {
        "reentrancy":       "value_conservation",
        "integer_overflow": "value_conservation",
        "unchecked_call":   "state_corruption",
        "tx_origin":        "state_corruption",
    }.get(vuln_class, "value_conservation")


# ── Selection ────────────────────────────────────────────────────────

def select_pilot(catalog, seed):
    rng = random.Random(seed)

    # Group eligible cases by (invguard_class, solidifi_sub)
    pools = defaultdict(list)
    for c in catalog:
        if c.get("eligible"):
            pools[(c["invguard_class"], c["solidifi_sub"])].append(c)

    selected = []

    for invguard_class, alloc in PILOT_ALLOCATION.items():
        for solidifi_sub, count in alloc["sub"].items():
            pool = pools.get((invguard_class, solidifi_sub), [])
            if not pool:
                print(f"  WARNING: no eligible cases for "
                      f"{invguard_class}/{solidifi_sub}")
                continue

            rng.shuffle(pool)
            picked = []
            hosts_used = defaultdict(int)
            contexts_used = set()
            keys_used = set()

            # Pass 1: one per host, diverse contexts
            hosts = sorted(set(c["host_id"] for c in pool))
            rng.shuffle(hosts)
            for host in hosts:
                if len(picked) >= count:
                    break
                candidates = [c for c in pool
                              if c["host_id"] == host
                              and c["dedup_key"] not in keys_used]
                if not candidates:
                    continue
                # Prefer unseen context
                candidates.sort(
                    key=lambda c: (c["context"] not in contexts_used,
                                   bool(c.get("clean_contract"))),
                    reverse=True)
                p = candidates[0]
                picked.append(p)
                hosts_used[host] += 1
                contexts_used.add(p["context"])
                keys_used.add(p["dedup_key"])

            # Pass 2: fill remaining (max 2 per host)
            if len(picked) < count:
                rest = [c for c in pool
                        if c not in picked
                        and c["dedup_key"] not in keys_used
                        and hosts_used[c["host_id"]] < MAX_PER_HOST]
                rng.shuffle(rest)
                for c in rest:
                    if len(picked) >= count:
                        break
                    picked.append(c)
                    hosts_used[c["host_id"]] += 1
                    keys_used.add(c["dedup_key"])

            # Pass 3: relax host cap if still short
            if len(picked) < count:
                rest2 = [c for c in pool
                         if c not in picked
                         and c["dedup_key"] not in keys_used]
                rng.shuffle(rest2)
                for c in rest2:
                    if len(picked) >= count:
                        break
                    picked.append(c)
                    keys_used.add(c["dedup_key"])

            selected.extend(picked)
            print(f"  {invguard_class:20s} / {solidifi_sub:25s}: "
                  f"{len(picked):2d}/{count} selected "
                  f"({len(set(c['host_id'] for c in picked))} hosts, "
                  f"{len(set(c['context'] for c in picked))} contexts)")

    return selected


# ── Manifest builder ─────────────────────────────────────────────────

def build_entry(case, idx):
    parsed = parse_sol(case["file"])
    tf = pick_target_function(parsed, case["invguard_class"])
    stem = (f"sfi_{case['invguard_class']}_"
            f"{case['solidifi_sub']}_"
            f"h{case['host_id']}_"
            f"{Path(case['file']).stem}")

    return {
        "stem": stem,
        "contract": case["file"],
        "clean_contract": case.get("clean_contract", ""),
        "target_function": tf,
        "solidifi_category": case["dir_name"],
        "solidifi_sub": case["solidifi_sub"],
        "host_id": case["host_id"],
        "context": case.get("context", ""),
        "extra_env": {
            "INVGUARD_VULN_CLASS": case["invguard_class"],
            "INVGUARD_IMPACT_POLICY": impact_policy(case["invguard_class"]),
        },
    }


# ── Main ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Select 20 pilot SolidiFI cases for InvGuard evaluation")
    ap.add_argument("--solidifi-root", required=True,
                    help="Path to cloned SolidiFI-benchmark repo")
    ap.add_argument("--out", default="solidifi_pilot20.json")
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    ap.add_argument("--skip-compile", action="store_true",
                    help="Skip compilation check (faster)")
    args = ap.parse_args()

    print(f"{'='*60}")
    print(f"  SolidiFI Pilot-20 Selector (seed={args.seed})")
    print(f"{'='*60}\n")

    # ── Step 1: Discover ──
    print("[1/5] Scanning SolidiFI ...", flush=True)
    cases = discover(args.solidifi_root)
    print(f"      Found {len(cases)} mutants in supported categories\n")

    if not cases:
        print("ERROR: no .sol files found. Check --solidifi-root path.")
        print(f"       Tried: {args.solidifi_root}/buggy_contracts/")
        sys.exit(1)

    by_class = defaultdict(int)
    by_sub = defaultdict(int)
    for c in cases:
        by_class[c["invguard_class"]] += 1
        by_sub[c["solidifi_sub"]] += 1
    print("      Per InvGuard class:")
    for k in sorted(by_class):
        print(f"        {k:20s}: {by_class[k]:5d}")
    print("      Per SolidiFI subcategory:")
    for k in sorted(by_sub):
        print(f"        {k:25s}: {by_sub[k]:5d}")

    funnel = {
        "total_scanned": len(cases),
        "per_class_raw": dict(by_class),
        "per_sub_raw": dict(by_sub),
    }

    # ── Step 2: Parse and classify ──
    print("\n[2/5] Parsing contracts ...", flush=True)
    for c in cases:
        parsed = parse_sol(c["file"])
        c["pragma"] = parsed["pragma"]
        c["contracts"] = parsed["contracts"]
        c["functions"] = parsed["functions"]
        c["lines"] = parsed["lines"]
        c["reachable"] = is_reachable(parsed)
        c["context"] = classify_context(c, parsed)
        c["dedup_key"] = dedup_key(c, parsed)

    reachable = [c for c in cases if c["reachable"]]
    funnel["reachable"] = len(reachable)
    print(f"      {len(reachable)}/{len(cases)} have reachable public functions")

    # ── Step 3: Compile check ──
    if not args.skip_compile:
        print(f"\n[3/5] Checking compilation ({len(reachable)} files) ...",
              flush=True)
        for i, c in enumerate(reachable):
            ok, err = try_compile(c["file"])
            c["compiles"] = ok
            c["compile_error"] = err
            if (i + 1) % 100 == 0 or (i + 1) == len(reachable):
                done = sum(1 for x in reachable[:i+1] if x.get("compiles"))
                print(f"      {i+1}/{len(reachable)} checked, "
                      f"{done} compile OK", flush=True)
        compilable = [c for c in reachable if c["compiles"]]
        funnel["compilable"] = len(compilable)
    else:
        print("\n[3/5] Skipping compilation check (--skip-compile)")
        for c in reachable:
            c["compiles"] = True
            c["compile_error"] = ""
        compilable = reachable
        funnel["compilable"] = len(compilable)

    # ── Step 4: Deduplicate ──
    print(f"\n[4/5] Deduplicating ...", flush=True)
    seen = set()
    deduped = []
    for c in compilable:
        if c["dedup_key"] not in seen:
            seen.add(c["dedup_key"])
            deduped.append(c)
    funnel["after_dedup"] = len(deduped)
    print(f"      {len(deduped)} unique after dedup "
          f"(removed {len(compilable) - len(deduped)} duplicates)")

    for c in deduped:
        c["eligible"] = True

    # ── Step 5: Select ──
    print(f"\n[5/5] Selecting 20 cases (seed={args.seed}) ...", flush=True)
    selected = select_pilot(deduped, args.seed)
    funnel["selected"] = len(selected)

    # ── Write outputs ──
    out_base = Path(args.out).stem
    out_dir = Path(args.out).parent

    manifest = [build_entry(c, i) for i, c in enumerate(selected)]
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)

    funnel_path = out_dir / f"{out_base}_funnel.json"
    with open(funnel_path, "w") as f:
        json.dump(funnel, f, indent=2)

    catalog_path = out_dir / f"{out_base}_catalog.csv"
    sel_keys = {c["dedup_key"] for c in selected}
    with open(catalog_path, "w", newline="") as f:
        cols = ["filename", "invguard_class", "solidifi_sub", "host_id",
                "pragma", "reachable", "compiles", "context", "dedup_key",
                "selected"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in cases:
            c["selected"] = c.get("dedup_key", "") in sel_keys
            w.writerow(c)

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"  PILOT-20 SELECTION COMPLETE")
    print(f"{'='*60}")
    print(f"\n  Funnel:")
    print(f"    Raw mutants (4 InvGuard classes): {funnel['total_scanned']}")
    print(f"    Reachable:                        {funnel['reachable']}")
    print(f"    Compilable:                       {funnel['compilable']}")
    print(f"    After dedup:                      {funnel['after_dedup']}")
    print(f"    Selected:                         {funnel['selected']}")

    print(f"\n  Selected cases:")
    for m in manifest:
        print(f"    {m['stem']}")
        print(f"      contract:  {m['contract']}")
        print(f"      target_fn: {m['target_function']}")
        print(f"      class:     {m['extra_env']['INVGUARD_VULN_CLASS']}")
        print(f"      clean:     {m['clean_contract'] or '(none)'}")
        print()

    print(f"  Outputs:")
    print(f"    Manifest:  {args.out}")
    print(f"    Funnel:    {funnel_path}")
    print(f"    Catalog:   {catalog_path}")
    print(f"\n  Next steps:")
    print(f"    1. Review the 20 cases above")
    print(f"    2. Run baselines:")
    print(f"       python solidifi_run_baselines.py \\")
    print(f"           --manifest {args.out} --tool solgpt \\")
    print(f"           --out-dir results/solidifi_baselines")
    print(f"    3. Run InvGuard:")
    print(f"       python run_batch.py \\")
    print(f"           --manifest {args.out} --tag solidifi_pilot20")


if __name__ == "__main__":
    main()
