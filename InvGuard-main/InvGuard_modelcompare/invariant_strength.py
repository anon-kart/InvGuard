# invariant_strength.py
import os
import re
import json
import tempfile
from typing import Dict, List, Tuple, Any, Optional

from invariant_validator import validate_invariants_on_contract


# ----------------------------
# Simple contract mutants
# ----------------------------
def generate_mutants(sol_src: str, max_mutants: int = 12) -> List[Tuple[str, str]]:
    muts: List[Tuple[str, str]] = []

    # M1: remove first require(...)
    m = re.search(r"^\s*require\s*\(.*?\)\s*;\s*$", sol_src, re.M)
    if m:
        mutant = sol_src[:m.start()] + "// MUTATION: require removed\n" + sol_src[m.end():]
        muts.append(("drop_require_1", mutant))

    # M2: flip >= to > in first require
    m = re.search(r"(require\s*\(.*?)(>=)(.*?\)\s*;)", sol_src, re.S)
    if m:
        mutant = sol_src[:m.start(2)] + ">" + sol_src[m.end(2):]
        muts.append(("flip_ge_to_gt", mutant))

    # M3: += to -= (first occurrence)
    m = re.search(r"\+=", sol_src)
    if m:
        mutant = sol_src[:m.start()] + "-=" + sol_src[m.end():]
        muts.append(("plus_eq_to_minus_eq", mutant))

    # M4: -= to += (first occurrence)
    m = re.search(r"-=", sol_src)
    if m:
        mutant = sol_src[:m.start()] + "+=" + sol_src[m.end():]
        muts.append(("minus_eq_to_plus_eq", mutant))

    # M5 (GENERALIZED): remove any mapping subtraction update.
    # Old version was hardcoded to "balances[msg.sender] = bal - amount".
    # New version matches any pattern: mapping[key] = expr - varname;
    # This covers escrowBalance, shares, points, funds, etc.
    m = re.search(
        r"(\w+)\s*\[[\w.\s]*\]\s*=\s*[\w\[\].\s]+\s*-\s*(\w+)\s*;",
        sol_src
    )
    if m:
        mutant = sol_src[:m.start()] + f"// MUTATION: subtraction update removed ({m.group(0).strip()})\n" + sol_src[m.end():]
        muts.append(("remove_mapping_subtraction", mutant))

    # M6: relax msg.value > 0 to >= 0
    mutant = re.sub(r"msg\.value\s*>\s*0", "msg.value >= 0", sol_src, count=1)
    if mutant != sol_src:
        muts.append(("relax_msg_value_guard", mutant))

    # M7: remove require(ok,...) or require(ok)
    m = re.search(r"^\s*require\s*\(\s*ok[\s,)].*?\)\s*;\s*$", sol_src, re.M)
    if m:
        mutant = sol_src[:m.start()] + "// MUTATION: require(ok) removed\n" + sol_src[m.end():]
        muts.append(("drop_require_ok", mutant))

    # M8 (NEW): CEI violation — move state update AFTER external call.
    # High-value mutation for reentrancy invariants.
    # Detects pattern: state_update; external_call → swaps them.
    _cei_pattern = re.search(
        r"(\w[\w]*\s*\[[\w.\s]*\]\s*(?:[-+]?=)[^;]+;\n)([ \t]*\([^)]*\)\s*=\s*(?:[\w.\s]+)\.(?:call|send|transfer)[^;]+;)",
        sol_src, re.S
    )
    if _cei_pattern:
        # swap: put the call before the state update
        state_upd = _cei_pattern.group(1)
        ext_call  = _cei_pattern.group(2)
        mutant = (
            sol_src[:_cei_pattern.start()]
            + ext_call + "\n"
            + state_upd
            + sol_src[_cei_pattern.end():]
        )
        muts.append(("cei_swap", mutant))

    # M9 (NEW): remove nonReentrant modifier if present.
    mutant = re.sub(r"\bnonReentrant\b", "", sol_src, count=1)
    if mutant != sol_src:
        muts.append(("drop_nonreentrant", mutant))

    # M10: remove second require() — catches cases where M1 removes the wrong one
    requires = list(re.finditer(r"^\s*require\s*\(.*?\)\s*;\s*$", sol_src, re.M))
    if len(requires) >= 2:
        m2 = requires[1]
        mutant = sol_src[:m2.start()] + "// MUTATION: require2 removed\n" + sol_src[m2.end():]
        muts.append(("drop_require_2", mutant))

    return muts[:max_mutants]


# ----------------------------
# Invariant line normalization (REQUIRED FIX)
# ----------------------------
def _fix_bad_implication_parens(line: str) -> str:
    """
    Robustly fix the common broken implication guard:

      (meta.revert_taken == false -> X)
      meta.revert_taken==false->X
      ( meta.revert_taken == true  ->  X )

    into:

      ((meta.revert_taken == false) -> X)
      (meta.revert_taken == false) -> X    (if caller doesn't wrap outer parens)
    """
    s = (line or "").strip()
    if not s:
        return s

    # normalize implication token
    s = s.replace("=>", "->")
    s = re.sub(r"\s+", " ", s).strip()

    # Replace ANY "meta.revert_taken == <bool> ->" with "(meta.revert_taken == <bool>) ->"
    # (works whether or not it is preceded by '(')
    s = re.sub(
        r"meta\.revert_taken\s*==\s*(false|true)\s*->",
        r"(meta.revert_taken == \1) ->",
        s,
        flags=re.IGNORECASE,
    )

    return s


# ----------------------------
# Tautology / triviality detection
# ----------------------------
def is_tautology_like(inv: str) -> bool:
    """
    IMPORTANT (REQUIRED CHANGE):
    - Do NOT treat "select(... ) >= 0" as a tautology.
    - Tautology means identity / self-evident truths only.

    Strengthening per "guide Flow-2 with useful invariants":
    - Consider implication with a tautological consequent as tautology-like:
        (G -> (X == X))
        (G -> true)
    - Consider meta.* identity (meta.sender == meta.sender) tautology-like.
    """
    s = (inv or "").strip()
    if not s:
        return True

    # Normalize implication token
    s = s.replace("=>", "->")

    # If it's an implication, check consequent for tautology / 'true'
    if "->" in s:
        parts = s.split("->", 1)
        rhs = parts[1].strip()
        rhs = rhs.strip()
        # strip one layer of outer parens
        if rhs.startswith("(") and rhs.endswith(")"):
            rhs_inner = rhs[1:-1].strip()
            if rhs_inner.count("(") == rhs_inner.count(")"):
                rhs = rhs_inner

        if rhs.lower() == "true":
            return True

        # rhs: x == x
        if re.match(r"^\s*(.+?)\s*==\s*\1\s*$", rhs):
            return True

        # rhs: meta.sender == meta.sender, pre.x == pre.x, select(...) == select(...)
        if re.search(r"\b(pre|post|meta)\.([A-Za-z_]\w*)\s*==\s*\1\.\2\b", rhs):
            return True

        # if consequent is tautology-like, treat the whole invariant as tautology-like
        # (do not re-check entire string further)
        return False  # continue to evaluate full-string below? No: we already handled RHS tautology cases.

    # Non-implication cases:

    # bare literal truth: true / (true) / ((true)) — strip balanced outer parens
    _bare = s
    while _bare.startswith("(") and _bare.endswith(")") and _bare[1:-1].count("(") == _bare[1:-1].count(")"):
        _bare = _bare[1:-1].strip()
    if _bare.lower() == "true":
        return True

    # x == x
    if re.match(r"^\s*(.+?)\s*==\s*\1\s*$", s):
        return True

    # pre.x == pre.x or post.x == post.x or meta.x == meta.x
    if re.search(r"\b(pre|post|meta)\.([A-Za-z_]\w*)\s*==\s*\1\.\2\b", s):
        return True

    # owner == owner (kept for backward compatibility)
    if re.search(r"\b(pre|post)\.owner\s*==\s*(pre|post)\.owner\b", s):
        # also catches exact identity like pre.owner == pre.owner or post.owner == post.owner
        if re.search(r"\b(pre|post)\.owner\s*==\s*\1\.owner\b", s):
            return True
        # pre.owner == post.owner is NOT tautology
        return False

    return False


def _coverage_features(inv: str) -> Dict[str, int]:
    return {
        "has_pre": 1 if "pre." in inv else 0,
        "has_post": 1 if "post." in inv else 0,
        "has_arg": 1 if "arg." in inv else 0,
        "has_meta": 1 if "meta." in inv else 0,
        "has_select": 1 if "select(" in inv else 0,
        "has_relation": 1 if ("pre." in inv and "post." in inv) else 0,
    }


def _is_trivial(inv: str) -> bool:
    """
    IMPORTANT (REQUIRED CHANGE):
    - ">= 0" is TRIVIAL/WEAK, not a tautology.

    Strengthening for Flow-2 guidance:
    - Also treat explicit boolean self-evidence as trivial:
        (G -> true)   (though these are usually caught by tautology_like if RHS is 'true')
    """
    s = inv.replace(" ", "")
    m = re.match(r"^(.*?)(==|>=|<=)(.*?)$", s)
    if m and m.group(1) == m.group(3):
        return True

    if re.search(r">=\s*0\b", inv):
        return True

    # direct 'true' (or guarded true)
    inv_norm = inv.strip().lower().replace("=>", "->")
    if inv_norm == "true":
        return True
    if "->" in inv_norm:
        rhs = inv_norm.split("->", 1)[1].strip()
        if rhs == "true" or rhs == "(true)":
            return True

    return False


# ---------------------------------------------------------
# Canonicalization for matching & dedup
# ---------------------------------------------------------
def _canonicalize(inv: str) -> str:
    s = (inv or "").strip()
    if not s:
        return ""

    s = s.replace("=>", "->")
    s = re.sub(r"\s+", " ", s).strip()

    # repair missing parens (end-of-line balancing only)
    diff = s.count("(") - s.count(")")
    if diff > 0:
        s = s + (")" * diff)

    def _balanced(x: str) -> bool:
        return x.count("(") == x.count(")")

    while s.startswith("(") and s.endswith(")") and _balanced(s[1:-1]):
        inner = s[1:-1].strip()
        if not inner or not _balanced(inner):
            break
        s = inner

    return s


def load_invariants_raw(path: str) -> List[str]:
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            if s.endswith(";"):
                s = s[:-1].strip()

            # repair implication formatting early
            s = _fix_bad_implication_parens(s)

            out.append(s)
    return out


# ----------------------------
# Per-invariant scoring helper
# ----------------------------
def score_invariant(
    inv: str,
    killed: int,
    mutants_ran: int,
    strong_threshold: float,
    min_kill_rate_for_strong: float,
    medium_threshold: float,
    min_kill_rate_for_medium: float,
    kills_validated_exploit: bool = False,
) -> Dict[str, Any]:
    """
    Strength of an invariant, defined on a single, documented principle:

      An invariant is STRONG to the extent that it DETECTS faults.

    The primary, semantic signal is the mutation KILL RATE: the fraction of
    behaviour-changing mutants of the contract that this invariant flags as
    violated. Mutation kill-rate is a standard, well-understood proxy for fault
    detection power, which is why it is the sole basis for tiering here.

    Coverage (whether the invariant relates pre/post state, indexes mappings,
    etc.) is used ONLY as a tie-breaker and as a guard against vacuous STRONG
    labels — it is deliberately NOT added into the tier decision, because
    "mentions more variables" is a syntactic property and must not let a weak
    invariant outrank a tight one. This removes the previous unmotivated
    0.65/0.30/0.05 weighting.

    Optionally, if the invariant is known to flag a CONCRETELY VALIDATED exploit
    (kills_validated_exploit=True, supplied by Flow-2), it is promoted to STRONG.
    This ties invariant strength (Point 5) directly to demonstrated exploit
    coverage (Point 1): an invariant that actually catches a real, executed
    attack is strong by definition, regardless of the synthetic mutant score.

    `score` in [0,1] is reported for ranking/inspection only and equals the
    kill rate (with a small, explicit coverage tie-breaker in the last decimal);
    it is NOT a separate acceptance criterion.
    """
    feats = _coverage_features(inv)
    # Coverage in [0,1]: a real pre→post relation is the most informative single
    # feature, so it dominates; the rest are minor descriptors.
    cov = min(
        1.0,
        0.6 * feats["has_relation"]
        + 0.1 * feats["has_pre"]
        + 0.1 * feats["has_post"]
        + 0.1 * feats["has_select"]
        + 0.1 * feats["has_meta"],
    )
    has_real_relation = bool(feats["has_relation"] or feats["has_select"])

    kr = (killed / mutants_ran) if mutants_ran > 0 else 0.0

    # --- always-weak cases, with distinct reasons ---
    if is_tautology_like(inv):
        return {
            "kill_rate": kr, "coverage_score": round(cov, 3),
            "trivial": True, "score": 0.0, "tier": "weak",
            "weak_reason": "tautology", "kills_validated_exploit": kills_validated_exploit,
        }
    if _is_trivial(inv):
        return {
            "kill_rate": kr, "coverage_score": round(cov, 3),
            "trivial": True, "score": round(0.5 * kr, 3), "tier": "weak",
            "weak_reason": "trivial", "kills_validated_exploit": kills_validated_exploit,
        }

    # Ranking score: kill rate is the signal; coverage only breaks ties in the
    # third decimal so it can never reorder across a real kill-rate gap.
    score = round(min(1.0, kr + 0.01 * cov), 3)

    # --- exploit-coverage promotion (ties Point 5 to Point 1) ---
    if kills_validated_exploit:
        return {
            "kill_rate": kr, "coverage_score": round(cov, 3),
            "trivial": False, "score": max(score, 0.99), "tier": "strong",
            "weak_reason": None, "kills_validated_exploit": True,
        }

    # --- tiering: purely on kill rate, with a non-vacuous-coverage guard ---
    # STRONG requires BOTH a substantive kill rate AND a real state relation, so
    # killing one trivial mutant can no longer alone yield STRONG.
    if kr >= min_kill_rate_for_strong and has_real_relation:
        tier, weak_reason = "strong", None
    elif kr >= min_kill_rate_for_medium:
        tier, weak_reason = "medium", None
    else:
        tier = "weak"
        weak_reason = "low_kill_rate" if kr < min_kill_rate_for_medium else "low_coverage"

    return {
        "kill_rate": kr, "coverage_score": round(cov, 3),
        "trivial": False, "score": score, "tier": tier,
        "weak_reason": weak_reason, "kills_validated_exploit": False,
    }


# ----------------------------
# Main entry
# ----------------------------
def score_invariants_on_contract(
    repo_root: str,
    original_contract_src: str,
    invariants_txt_path: str,
    z3checker_root: Optional[str] = None,
    function_name: Optional[str] = None,
    max_mutants: int = 12,
    # Tiering thresholds are expressed as KILL RATES (fraction of behaviour-
    # changing mutants flagged), not raw counts, so they are independent of how
    # many mutants happened to compile. STRONG = catches a substantial share of
    # injected faults AND expresses a real state relation; MEDIUM = catches at
    # least a modest share; below that = WEAK. These bands are reported in the
    # paper and can be sensitivity-tested; STRONG is deliberately well above
    # "one mutant" so a single trivial kill cannot earn the top tier.
    strong_threshold: float = 0.45,          # retained for API compat (unused in tiering)
    min_kill_rate_for_strong: float = 0.30,  # ≥30% of mutants killed → STRONG (+ real relation)
    medium_threshold: float = 0.25,          # retained for API compat (unused in tiering)
    min_kill_rate_for_medium: float = 0.10,  # ≥10% of mutants killed → at least MEDIUM
    # Optional: set of invariant strings known (from Flow-2 concrete execution)
    # to flag a VALIDATED exploit. Such invariants are promoted to STRONG,
    # linking invariant strength (Point 5) to demonstrated exploit coverage
    # (Point 1). When None, scoring falls back to mutation kill-rate alone.
    _exploit_killing_invariants: Optional[set] = None,
) -> Dict[str, Any]:

    inv_lines_raw = load_invariants_raw(invariants_txt_path)

    inv_lines: List[str] = []
    seen = set()
    for x in inv_lines_raw:
        # apply fix -> canonicalize -> apply fix again (outer-paren stripping can expose patterns)
        cx = _fix_bad_implication_parens(x)
        cx = _canonicalize(cx)
        cx = _fix_bad_implication_parens(cx)
        cx = _canonicalize(cx)

        if not cx or cx in seen:
            continue
        seen.add(cx)
        inv_lines.append(cx)

    # If function_name is None, Z3Checker global mode does NOT define arg.*
    if function_name is None:
        inv_lines = [inv for inv in inv_lines if "arg." not in inv]

    mutants = generate_mutants(original_contract_src, max_mutants=max_mutants)

    tmp_root = tempfile.mkdtemp(prefix="inv_strength_")

    # normalized invariants file for mutants
    normalized_invariants_path = os.path.join(tmp_root, "invariants.normalized.txt")
    with open(normalized_invariants_path, "w", encoding="utf-8") as f:
        f.write("\n".join(inv_lines) + ("\n" if inv_lines else ""))

    killed_counts = {inv: 0 for inv in inv_lines}
    mutants_ran = 0
    mutant_meta = []

    for name, msrc in mutants:
        mpath = os.path.join(tmp_root, f"{name}.sol")
        with open(mpath, "w", encoding="utf-8") as f:
            f.write(msrc)

        try:
            res = validate_invariants_on_contract(
                contract_path=mpath,
                invariants_txt_path=normalized_invariants_path,
                function_name=function_name,
                z3checker_root=z3checker_root,
                repo_root=repo_root,
            )
        except Exception as e:
            mutant_meta.append({"name": name, "compiled": False, "error": str(e)})
            continue

        mutants_ran += 1
        mutant_meta.append({"name": name, "compiled": True})

        failed = {
            _canonicalize(_fix_bad_implication_parens(f.get("line", "")))
            for f in res.get("failed", [])
            if f.get("line")
        }

        for inv in inv_lines:
            if inv in failed:
                killed_counts[inv] += 1

    scores_out: List[Dict[str, Any]] = []
    strong: List[str] = []
    medium: List[str] = []
    weak: List[str] = []

    for inv in inv_lines:
        meta = score_invariant(
            inv,
            killed_counts.get(inv, 0),
            mutants_ran,
            strong_threshold,
            min_kill_rate_for_strong,
            medium_threshold,
            min_kill_rate_for_medium,
            kills_validated_exploit=bool(
                _exploit_killing_invariants and inv in _exploit_killing_invariants
            ),
        )
        entry = {
            "invariant": inv,
            "killed": killed_counts.get(inv, 0),
            "mutants_ran": mutants_ran,
            **meta,
        }
        scores_out.append(entry)

        if meta["tier"] == "strong":
            strong.append(inv)
        elif meta["tier"] == "medium":
            medium.append(inv)
        else:
            weak.append(inv)

    return {
        "scores": scores_out,
        "strong": strong,
        "medium": medium,
        "weak": weak,
        "mutants": mutant_meta,
    }