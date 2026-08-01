# invariant_validator.py
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

from invguard_adapter import run_invguard_core


# ============================================================
# Fail-closed invariant filtering policy
# ============================================================

BAD_INVARIANT_MARKERS = [
    "UNVERIFIED_UNSOUND",
    "REJECTED_UNSUPPORTED",
    "TRANSLATION_FAILED",
    "BUILTIN_FALLBACK",
    "LLM_INVARIANT_NOT_TRANSLATED",
    "PLACEHOLDER_INVARIANT",
    "NOT_A_REAL_VERIFIED_INVARIANT",
    "TRIVIAL_INVARIANT_NOT_USEFUL",
    "REMOVED_FROM_VERIFIED_BY_FINAL_SAFETY_SCRUB",
    "reason=",
]

_PLACEHOLDER_INV_RE = re.compile(r"^<inv_\d+>$")


def _is_placeholder_invariant(s: str) -> bool:
    return bool(_PLACEHOLDER_INV_RE.fullmatch((s or "").strip()))


def _is_trivial_invariant(s: str) -> bool:
    t = (s or "").strip().lower()

    return t in {
        "true",
        "(true)",
        "trivial true",
        "meta.sender == meta.sender",
        "(meta.sender == meta.sender)",
        "false == false",
        "true == true",
    }


def _is_real_verified_invariant(line: str) -> bool:
    """
    Final fail-closed check before any invariant can be counted as verified.

    This rejects:
      - comments / blank lines
      - placeholders like <inv_1>
      - trivial tautologies
      - unsound/rejected/fallback markers
    """
    s = (line or "").strip()

    if not s:
        return False

    if s.startswith("#") or s.startswith("//"):
        return False

    if _is_placeholder_invariant(s):
        return False

    if _is_trivial_invariant(s):
        return False

    if any(marker in s for marker in BAD_INVARIANT_MARKERS):
        return False

    return True


def _dedup_verified(lines: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()

    for line in lines or []:
        s = (line or "").strip()

        if not _is_real_verified_invariant(s):
            continue

        key = re.sub(r"\s+", " ", s)

        if key in seen:
            continue

        seen.add(key)
        out.append(s)

    return out


# ============================================================
# Syntax-only cleaning helpers
# ============================================================

def _balance_parens_end(s: str) -> str:
    """
    If we have more '(' than ')', append missing ')' at end.
    This is a pragmatic robustness step for LLM-generated lines.
    """
    if not s:
        return s

    diff = s.count("(") - s.count(")")

    if diff > 0:
        s = s + (")" * diff)

    return s


def _fix_bad_implication_parens(line: str) -> str:
    """
    Make implication operands properly parenthesized for Z3Checker's DSL.

    We have seen bad lines like:
      (meta.revert_taken == false -> ( ... ))
    or:
      meta.revert_taken == false -> ( ... )

    We want:
      ((meta.revert_taken == false) -> ( ... ))

    Also normalizes '=>' to '->' and wraps the whole line.
    """
    s = (line or "").strip()

    if not s:
        return s

    # Normalize implication token early.
    s = s.replace("=>", "->")

    # Case A: line starts with "(meta.revert_taken == false -> ..."
    s = re.sub(
        r"^\(\s*meta\.revert_taken\s*==\s*(false|true)\s*->\s*",
        r"((meta.revert_taken == \1) -> ",
        s,
    )

    # Case B: line contains "meta.revert_taken == false ->" without parentheses.
    s = re.sub(
        r"\bmeta\.revert_taken\s*==\s*(false|true)\s*->\s*",
        r"(meta.revert_taken == \1) -> ",
        s,
    )

    # If implication exists, ensure whole line is wrapped.
    st = s.strip()

    if "->" in s:
        if not (st.startswith("(") and st.endswith(")")):
            s = "(" + s + ")"

    s = _balance_parens_end(s)
    return s


def _rewrite_known_bad_invariants(line: str) -> str:
    """
    IMPORTANT:
    This function is intentionally conservative by default.

    We do NOT perform semantic weakening unless explicitly enabled through
    allow_semantic_rewrites=True in _clean_invariants_file.

    Keeping this function preserves backward compatibility with callers who
    relied on it, but it is only used when allow_semantic_rewrites=True.
    """
    s = (line or "").strip()

    if not s:
        return s

    # Example semantic weakening, DISABLED by default:
    # select(pre|post.balances, ...) > 0  ==>  >= 0
    s = re.sub(
        r"(select\(\s*(?:pre|post)\.balances\s*,\s*[^)]+\)\s*)>\s*0\b",
        r"\1>= 0",
        s,
    )

    return s


def _clean_invariants_file(
    in_path: str,
    out_path: str,
    *,
    allow_semantic_rewrites: bool = False,
) -> str:
    """
    Z3Checker's invariant parser can choke on headers/comments/formatting.

    This writes a sanitized invariants file:
      - drops blank lines
      - drops comments
      - drops known unsafe markers
      - drops placeholders like <inv_1>
      - drops trivial tautologies
      - strips trailing ';'
      - fixes implication formatting
      - balances parentheses

    Reviewer-proof rule:
      - By default, we do NOT do semantic rewrites.
      - If allow_semantic_rewrites=True, rewrites are meaning-changing and
        must be reported as rewritten invariants, not original invariants.
    """
    cleaned: List[str] = []

    with open(in_path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()

            if not s:
                continue

            if s.startswith("#") or s.startswith("//"):
                continue

            if any(marker in s for marker in BAD_INVARIANT_MARKERS):
                continue

            if _is_placeholder_invariant(s):
                continue

            if _is_trivial_invariant(s):
                continue

            if s.endswith(";"):
                s = s[:-1].strip()

            # 1) implication formatting fix, syntax-only.
            s = _fix_bad_implication_parens(s)

            # 2) optional semantic rewrites, OFF by default.
            if allow_semantic_rewrites:
                s = _rewrite_known_bad_invariants(s)

            # 3) final balance after formatting/rewrite.
            s = _balance_parens_end(s)

            if not _is_real_verified_invariant(s):
                continue

            cleaned.append(s)

    Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned) + ("\n" if cleaned else ""))

    return out_path


# ============================================================
# Main validation API
# ============================================================

def validate_invariants_on_contract(
    contract_path: str,
    invariants_txt_path: str,
    function_name: Optional[str] = None,
    z3checker_root: Optional[str] = None,
    repo_root: Optional[str] = None,
    *,
    allow_semantic_rewrites: bool = False,
) -> Dict[str, Any]:
    """
    Runs InvGuard/Z3Checker against a contract using a set of invariants.

    ICSE-safe validation policy:
      - built-in fallback is rejected;
      - unsound model/invariants are rejected;
      - unknown/trusted invariants are diagnostics only;
      - placeholders are rejected;
      - trivial invariants are rejected;
      - validation succeeds only if at least one real verified invariant remains;
      - validation succeeds only if no invariant fails.

    Resolution order for Z3Checker root:
      1) z3checker_root
      2) repo_root/flow_1_files/Z3Checker
      3) <this_file_dir>/flow_1_files/Z3Checker

    Reviewer-proof default:
      - allow_semantic_rewrites=False.
    """
    if not os.path.exists(contract_path):
        raise FileNotFoundError(f"contract not found: {contract_path}")

    if not os.path.exists(invariants_txt_path):
        raise FileNotFoundError(f"invariants file not found: {invariants_txt_path}")

    if z3checker_root is None and repo_root is not None:
        z3checker_root = os.path.join(repo_root, "flow_1_files", "Z3Checker")

    if z3checker_root is None:
        here = os.path.dirname(os.path.abspath(__file__))
        z3checker_root = os.path.join(here, "flow_1_files", "Z3Checker")

    if not os.path.isdir(z3checker_root):
        raise FileNotFoundError(f"Z3Checker root not found: {z3checker_root}")

    # ------------------------------------------------------------
    # Sanitize invariants before passing to Z3Checker.
    # ------------------------------------------------------------
    tmp_dir = os.path.join(os.path.dirname(contract_path), "invariants_sanitized")
    sanitized_path = os.path.join(tmp_dir, "invariants.cleaned.txt")

    _clean_invariants_file(
        invariants_txt_path,
        sanitized_path,
        allow_semantic_rewrites=allow_semantic_rewrites,
    )

    # If sanitization removed everything, fail closed.
    try:
        with open(sanitized_path, "r", encoding="utf-8") as f:
            sanitized_lines = [
                ln.strip()
                for ln in f
                if ln.strip() and not ln.strip().startswith("#")
            ]
    except Exception:
        sanitized_lines = []

    sanitized_lines = [
        ln for ln in sanitized_lines
        if _is_real_verified_invariant(ln)
    ]

    if not sanitized_lines:
        return {
            "ok": False,
            "verified": [],
            "trusted": [],
            "unknown": [],
            "failed": [],
            "rejected": [],
            "unsound": [],
            "report_lines": [],
            "used_invariants_file": sanitized_path,
            "allow_semantic_rewrites": bool(allow_semantic_rewrites),
            "reason": "NO_REAL_INVARIANTS_AFTER_SANITIZATION",
        }

    # ------------------------------------------------------------
    # Run core checker through adapter.
    # ------------------------------------------------------------
    core = run_invguard_core(
        z3checker_root=z3checker_root,
        contract_path=contract_path,
        invariants_txt_path=sanitized_path,
        function_name=function_name,
    )

    # ------------------------------------------------------------
    # Fail-closed post-check policy.
    # ------------------------------------------------------------

    # 1) Built-in fallback must never count as validation.
    if getattr(core, "used_builtin_fallback", False):
        return {
            "ok": False,
            "verified": [],
            "trusted": [],
            "unknown": getattr(core, "unknown", []) or getattr(core, "trusted", []) or [],
            "failed": [],
            "rejected": getattr(core, "rejected", []) or [],
            "unsound": getattr(core, "unsound", []) or [],
            "report_lines": getattr(core, "report_lines", []) or [],
            "used_invariants_file": sanitized_path,
            "allow_semantic_rewrites": bool(allow_semantic_rewrites),
            "reason": "BUILTIN_FALLBACK_IGNORED_NO_LLM_INVARIANTS_VERIFIED",
        }

    # 2) Unsound results reject validation.
    if getattr(core, "unsound", []) or []:
        return {
            "ok": False,
            "verified": [],
            "trusted": [],
            "unknown": getattr(core, "unknown", []) or getattr(core, "trusted", []) or [],
            "failed": getattr(core, "failed", []) or [],
            "rejected": getattr(core, "rejected", []) or [],
            "unsound": getattr(core, "unsound", []) or [],
            "report_lines": getattr(core, "report_lines", []) or [],
            "used_invariants_file": sanitized_path,
            "allow_semantic_rewrites": bool(allow_semantic_rewrites),
            "reason": "UNSOUND_MODEL_OR_UNVERIFIED_INVARIANTS",
        }

    # 3) Failed invariants reject validation.
    failed = getattr(core, "failed", []) or []

    if failed:
        verified = _dedup_verified(getattr(core, "verified", []) or [])

        return {
            "ok": False,
            "verified": verified,
            "trusted": [],
            "unknown": getattr(core, "unknown", []) or getattr(core, "trusted", []) or [],
            "failed": failed,
            "rejected": getattr(core, "rejected", []) or [],
            "unsound": getattr(core, "unsound", []) or [],
            "report_lines": getattr(core, "report_lines", []) or [],
            "used_invariants_file": sanitized_path,
            "allow_semantic_rewrites": bool(allow_semantic_rewrites),
            "reason": "INVARIANTS_FAILED",
        }

    # 4) At least one real verified invariant must remain.
    verified = _dedup_verified(getattr(core, "verified", []) or [])

    if not verified:
        return {
            "ok": False,
            "verified": [],
            "trusted": [],
            "unknown": getattr(core, "unknown", []) or getattr(core, "trusted", []) or [],
            "failed": getattr(core, "failed", []) or [],
            "rejected": getattr(core, "rejected", []) or [],
            "unsound": getattr(core, "unsound", []) or [],
            "report_lines": getattr(core, "report_lines", []) or [],
            "used_invariants_file": sanitized_path,
            "allow_semantic_rewrites": bool(allow_semantic_rewrites),
            "reason": "NO_REAL_VERIFIED_INVARIANTS",
        }

    # 5) If every input invariant was rejected and none verified, reject.
    rejected = getattr(core, "rejected", []) or []
    unknown = getattr(core, "unknown", []) or getattr(core, "trusted", []) or []

    return {
        "ok": True,
        "verified": verified,
        # Kept for backward compatibility, but intentionally empty.
        "trusted": [],
        # Diagnostics only.
        "unknown": unknown,
        "failed": [],
        "rejected": rejected,
        "unsound": [],
        "report_lines": getattr(core, "report_lines", []) or [],
        "used_invariants_file": sanitized_path,
        "allow_semantic_rewrites": bool(allow_semantic_rewrites),
        "reason": "OK",
    }