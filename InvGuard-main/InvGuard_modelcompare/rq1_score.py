#!/usr/bin/env python3
"""
rq1_score.py  -  RQ1 aggregator for InvGetter invariant quality.

Reads the Flow-1 artifacts already emitted per contract (invariant_summary.json,
verified_invariants.scores.json, the VU/VM/VT/UT invariant files, and the
per-function verified summary) and produces the numbers behind Table 2 and
Figure 6:

  - accepted invariant count            (VU + VM + VT)
  - soundness rate                      accepted / (accepted + rejected + unsound)
  - strength tiers                      strong / medium / useful / weak
  - trivial / tautology count
  - category coverage                   accepted invariants per Table-1 class
  - correct-inference ratio, precision  (only when a ground-truth file is given)

It scans a results directory (results/<tag>/) for per-contract subdirectories,
or a single contract directory, and writes _rq1_summary.{json,csv}. It re-runs
nothing; missing artifacts are reported as coverage gaps rather than zero-filled.

Usage:
  python rq1_score.py --results results/<tag> [--groundtruth gt.json] [--config code_only]
  python rq1_score.py --contract-dir results/<tag>/<stem> --stem <stem>
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from invariant_strength import _canonicalize, is_tautology_like, _is_trivial
except Exception:
    def _canonicalize(inv):
        return re.sub(r"\s+", " ", inv or "").strip()

    def is_tautology_like(inv):
        return False

    def _is_trivial(inv):
        return False


CATEGORY_RULES = [
    ("Reentrancy", [r"\bdepth\b", r"revert_taken.*extern", r"nested",
                    r"\bcall\(external", r"\breentr"]),
    ("Delegatecall", [r"delegatecall", r"knownProxies", r"trustedCtx", r"walletlibrary"]),
    ("Access Control", [r"meta\.sender", r"\bowner\b", r"onlyOwner", r"roleSet",
                        r"tx\.origin", r"\bholder\b", r"manager", r"admin",
                        r"mindeposit", r"changeowner"]),
    ("Front-running", [r"commit", r"reveal", r"tx\.index", r"block\.number\s*mod",
                       r"randWindow", r"\bsalt\b", r"\brandom"]),
    ("Denial-of-Service", [r"gasleft", r"len\(", r"maxSize", r"\bbatch\b",
                           r"\bloop\b", r"timeout"]),
    ("External Calls", [r"externalCall", r"whitelist", r"\.call\b", r"\.send\b",
                        r"\.transfer\b", r"\bsuccess\b", r"\bpaid\b", r"payout"]),
    ("Uninitialized Storage", [r"accessedSlot", r"initFlag", r"0x00",
                               r"expectedDomain", r"initwallet", r"initialized"]),
    ("Overflow/Underflow", [r"post\.\w+\s*(<=|>=|==|<|>|!=)\s*.*pre\.\w+",
                            r"meta\.value", r"wrap", r"delta", r"paidTotal",
                            r"totalOwed", r"balance", r"supply", r"\bowed\b",
                            r"collectedfees", r"claimprice", r"currentbid",
                            r"\bfees?\b", r"\bprice\b", r"\bamount\b"]),
]


def categorize(inv):
    text = re.sub(r"\s+", " ", inv or "")
    for name, patterns in CATEGORY_RULES:
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                return name
    return "Uncategorized"


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _read_lines(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for ln in fh:
            s = ln.strip()
            if s and not s.startswith("#"):
                out.append(s)
    return out


def _find_one(stem_dir, name):
    hits = glob.glob(os.path.join(stem_dir, "**", name), recursive=True)
    return hits[0] if hits else None


def _gather_bucket(stem_dir, bucket):
    """Invariant text for a bucket (VU/VM/VT/UT): prefer the 'all' file, then
    the refined per-function file, then any per-function file."""
    prefs = [f"invariants.all.{bucket}.txt",
             f"invariants.*.refined.{bucket}.txt",
             f"invariants.*.{bucket}.txt"]
    for pat in prefs:
        hits = sorted(glob.glob(os.path.join(stem_dir, "**", pat), recursive=True))
        lines = []
        for h in hits:
            lines += _read_lines(h)
        if lines:
            seen, uniq = set(), []
            for x in lines:
                if x not in seen:
                    seen.add(x)
                    uniq.append(x)
            return uniq
    return []


def _score_perfunction_layout(stem_dir, stem):
    """Reader for the batch layout: verified_invariants.<fn>.summary.json plus
    verified_invariants.<fn>.txt (verified only). Reported invariants = verified;
    FP = trivial/vacuous among verified; the violated/rejected/unsound/unknown
    counts are the Z3 filter at work (funnel = RQ6), not RQ1 false positives."""
    summ_paths = sorted(glob.glob(os.path.join(
        stem_dir, "**", "verified_invariants.*.summary.json"), recursive=True))
    summ_paths = [p for p in summ_paths if ".global." not in os.path.basename(p)]
    if not summ_paths:
        return None

    verified_text, funnel = [], {"violated": 0, "rejected": 0,
                                 "unsound": 0, "unknown": 0}
    for sp in summ_paths:
        d = _load_json(sp) or {}
        for k, key in (("violated", "violated_count"), ("rejected", "rejected_count"),
                       ("unsound", "unsound_count"), ("unknown", "unknown_count")):
            funnel[k] = max(funnel[k], int(d.get(key, 0)))
        vf = sp.replace(".summary.json", ".txt")
        verified_text += _read_lines(vf)

    seen, verified = set(), []
    for x in verified_text:
        if x not in seen:
            seen.add(x)
            verified.append(x)

    trivial = sum(1 for inv in verified
                  if is_tautology_like(inv) or _is_trivial(inv))
    n = len(verified)
    rec = {
        "stem": stem, "have_summary": True, "have_scores": False,
        "VU": n, "VM": 0, "VT": trivial, "UT": 0,
        "rejected": funnel["rejected"], "unsound": funnel["unsound"],
        "unknown": funnel["unknown"], "violated": funnel["violated"],
        "meaningful": n, "trivial_noise": trivial, "fp": trivial,
        "precision": round((n - trivial) / n, 4) if n else None,
        "strong": 0, "medium": 0, "useful": 0, "weak": 0,
        "trivial_scored": trivial, "tautology": 0,
        "categories": {}, "meaningful_invariants": verified,
    }
    cats = {}
    for inv in verified:
        if is_tautology_like(inv):
            rec["tautology"] += 1
        c = categorize(inv)
        cats[c] = cats.get(c, 0) + 1
    rec["categories"] = cats
    return rec


def score_contract(stem_dir, stem):
    summ_path = _find_one(stem_dir, "invariant_summary.json")
    if not summ_path:
        alt = _score_perfunction_layout(stem_dir, stem)
        if alt is not None:
            return alt
    scores_path = _find_one(stem_dir, "verified_invariants.scores.json")

    rec = {
        "stem": stem,
        "have_summary": bool(summ_path),
        "have_scores": bool(scores_path),
        "VU": 0, "VM": 0, "VT": 0, "UT": 0,
        "rejected": 0, "unsound": 0, "unknown": 0,
        "meaningful": 0, "trivial_noise": 0,
        "precision": None, "fp": 0,
        "strong": 0, "medium": 0, "useful": 0, "weak": 0,
        "trivial_scored": 0, "tautology": 0,
        "categories": {},
        "meaningful_invariants": [],
    }

    summ = _load_json(summ_path) if summ_path else None
    if summ:
        for k in ("VU", "VM", "VT", "UT"):
            rec[k] = int((summ.get(k) or {}).get("count", 0))

    for sp in glob.glob(os.path.join(stem_dir, "**",
                                     "verified_invariants.*.summary.json"),
                        recursive=True):
        d = _load_json(sp) or {}
        rec["rejected"] += int(d.get("rejected_count", 0))
        rec["unsound"] += int(d.get("unsound_count", 0))
        rec["unknown"] += int(d.get("unknown_count", 0))

    vu_txt = _gather_bucket(stem_dir, "VU")
    vm_txt = _gather_bucket(stem_dir, "VM")
    meaningful_txt = vu_txt + vm_txt
    rec["meaningful_invariants"] = meaningful_txt

    rec["meaningful"] = rec["VU"] + rec["VM"]
    rec["trivial_noise"] = rec["VT"] + rec["UT"]
    candidates = (rec["meaningful"] + rec["trivial_noise"]
                  + rec["rejected"] + rec["unknown"])
    if candidates > 0:
        rec["precision"] = round(rec["meaningful"] / candidates, 4)
    rec["fp"] = rec["trivial_noise"] + rec["rejected"]

    scores = _load_json(scores_path) if scores_path else None
    if scores:
        for tier in ("strong", "medium", "useful", "weak"):
            rec[tier] = len(scores.get(tier, []) or [])
        for s in scores.get("scores", []) or []:
            if s.get("trivial"):
                rec["trivial_scored"] += 1

    cat_counts = {}
    for inv in meaningful_txt:
        if is_tautology_like(inv):
            rec["tautology"] += 1
        cat = categorize(inv)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    rec["categories"] = cat_counts
    return rec


def _var_tokens(inv):
    return set(re.findall(r"[A-Za-z_]\w+", _canonicalize(inv).lower()))


def apply_groundtruth(rec, gt_for_stem):
    critical = gt_for_stem.get("critical_invariants", [])
    rec["n_critical"] = len(critical)
    if not critical:
        rec["correct_inference_ratio"] = None
        return rec

    meaningful = rec["meaningful_invariants"]
    matched_gt = set()
    matched_inv = 0
    for a in meaningful:
        atoks = _var_tokens(a)
        acat = categorize(a)
        hit = False
        for i, g in enumerate(critical):
            gcat = g.get("category", "")
            gtoks = _var_tokens(g.get("formal", "") + " " + g.get("predicate", ""))
            overlap = len(atoks & gtoks)
            if (acat == gcat or gcat == "") and overlap >= 2:
                matched_gt.add(i)
                hit = True
        if hit:
            matched_inv += 1
    rec["correct_inference_ratio"] = round(len(matched_gt) / len(critical), 4)
    rec["gt_precision"] = round(matched_inv / len(meaningful), 4) if meaningful else None
    return rec


def aggregate(records):
    n = len(records)
    with_summary = [r for r in records if r["have_summary"]]
    def _mean(key):
        vals = [r[key] for r in records if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 4) if vals else None
    agg = {
        "n_contracts": n,
        "n_with_artifacts": len(with_summary),
        "mean_meaningful": _mean("meaningful"),
        "mean_fp": _mean("fp"),
        "mean_precision": _mean("precision"),
        "tier_totals": {t: sum(r[t] for r in records) for t in
                        ("strong", "medium", "useful", "weak")},
        "category_totals": {},
        "mean_correct_inference_ratio": _mean("correct_inference_ratio"),
        "mean_gt_precision": _mean("gt_precision"),
    }
    for r in records:
        for c, v in r["categories"].items():
            agg["category_totals"][c] = agg["category_totals"].get(c, 0) + v
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", help="results/<tag> directory")
    ap.add_argument("--contract-dir", help="single per-contract directory")
    ap.add_argument("--stem", help="stem name for --contract-dir")
    ap.add_argument("--groundtruth", help="ground-truth JSON keyed by stem")
    ap.add_argument("--config", default="", help="label written into output")
    ap.add_argument("--out-prefix", default=None)
    args = ap.parse_args()

    stem_dirs = []
    if args.contract_dir:
        stem_dirs = [(args.stem or os.path.basename(args.contract_dir.rstrip("/")),
                      args.contract_dir)]
        out_base = args.out_prefix or os.path.join(args.contract_dir, "_rq1")
    elif args.results:
        for d in sorted(glob.glob(os.path.join(args.results, "*"))):
            if os.path.isdir(d) and not os.path.basename(d).startswith("_"):
                stem_dirs.append((os.path.basename(d), d))
        out_base = args.out_prefix or os.path.join(args.results, "_rq1_summary")
    else:
        ap.error("provide --results or --contract-dir")

    gt = _load_json(args.groundtruth) if args.groundtruth else {}
    gt = gt or {}

    records = []
    for stem, d in stem_dirs:
        rec = score_contract(d, stem)
        if stem in gt:
            rec = apply_groundtruth(rec, gt[stem])
        records.append(rec)

    agg = aggregate(records)
    out = {"config": args.config, "aggregate": agg, "per_contract": records}
    with open(out_base + ".json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    cols = ["stem", "have_summary", "meaningful", "VU", "VM", "VT", "UT",
            "rejected", "unsound", "unknown", "fp", "precision",
            "strong", "medium", "useful", "weak", "trivial_scored", "tautology",
            "n_critical", "correct_inference_ratio", "gt_precision"]
    with open(out_base + ".csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)

    print(f"[rq1] contracts scored: {agg['n_contracts']} "
          f"(with artifacts: {agg['n_with_artifacts']})")
    print(f"[rq1] mean meaningful invariants (VU+VM): {agg['mean_meaningful']}")
    print(f"[rq1] mean FP/contract (trivial+rejected): {agg['mean_fp']}")
    print(f"[rq1] mean precision:            {agg['mean_precision']}")
    print(f"[rq1] strength tiers (total):    {agg['tier_totals']}")
    print(f"[rq1] category totals:           {agg['category_totals']}")
    if agg["mean_correct_inference_ratio"] is not None:
        print(f"[rq1] mean correct-inference:    {agg['mean_correct_inference_ratio']}")
        print(f"[rq1] mean gt-precision:         {agg['mean_gt_precision']}")
    print(f"[rq1] wrote {out_base}.json / .csv")


if __name__ == "__main__":
    main()
