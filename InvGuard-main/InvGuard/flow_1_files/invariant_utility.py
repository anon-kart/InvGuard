# InvGuard/flow_1_files/invariant_utility.py
from __future__ import annotations

import re
from typing import Dict, Tuple, Optional


# =============================================================================
# Utility / quality filter for refined invariants (Flow-1)
#
# Goal:
#   Prevent "refine -> tautology -> HOLDS -> exported as verified guidance"
#
# Use from agent.py:
#   from flow_1_files.invariant_utility import (
#       is_tautology,
#       is_trivial_weak,
#       has_security_signal,
#       utility_score,
#       classify_invariant_quality,
#   )
#
# Typical gate:
#   if is_tautology(refined) or is_trivial_weak(refined) or not has_security_signal(refined):
#       # discard or put into weak bucket (NOT used to guide Flow-2)
#       continue
# =============================================================================


_BOOL_LITERALS = {"true", "false"}

# Tokens that usually indicate the invariant "touches real semantics"
# (contract-agnostic; tuned for InvGuard DSL)
_SIGNAL_TOKENS = (
    "pre.",
    "post.",
    "select(",
    "store(",
    "arg.",
    "meta.value",
    "meta.sender",
    "meta.origin",
    "meta.revert_taken",
    "balances",
    "allowance",
    "owner",
    "admin",
    "ok",
    "total",
    "supply",
    "mint",
    "burn",
    "transfer",
)

# Functions typically expected to mutate state; if invariant is a noop/tautology there,
# it's extra-suspicious.
_MUTATING_FN_HINTS = (
    "deposit",
    "withdraw",
    "transfer",
    "mint",
    "burn",
    "approve",
    "swap",
    "buy",
    "sell",
    "borrow",
    "repay",
    "stake",
    "unstake",
    "claim",
    "redeem",
    "execute",
    "call",
    "delegate",
)


def _strip_outer_parens(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    while s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip()
        if inner.count("(") != inner.count(")"):
            break
        s = inner
    return s


def _canonicalize(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    s = s.replace("=>", "->")
    s = re.sub(r"\s+", " ", s).strip()

    # end-of-line paren repair only (safe)
    diff = s.count("(") - s.count(")")
    if diff > 0:
        s = s + (")" * diff)

    # conservatively peel redundant outer parentheses
    def _balanced(x: str) -> bool:
        return x.count("(") == x.count(")")

    while s.startswith("(") and s.endswith(")") and _balanced(s[1:-1]):
        inner = s[1:-1].strip()
        if not inner or not _balanced(inner):
            break
        s = inner

    return s


def _split_guard(inv: str) -> Tuple[str, str]:
    """
    If inv is '(G) -> RHS', return (G, RHS). Else ("", inv).
    """
    s = _canonicalize(inv)
    if "->" not in s:
        return "", s
    g, rhs = s.split("->", 1)
    return g.strip(), rhs.strip()


def _split_cmp(expr: str) -> Optional[Tuple[str, str, str]]:
    """
    Return (lhs, op, rhs) for a simple comparison.
    """
    s = (expr or "").strip()
    for op in ("==", "!=", ">=", "<=", ">", "<"):
        if op in s:
            a, b = s.split(op, 1)
            return a.strip(), op, b.strip()
    return None


def _is_boolean_atom(expr: str) -> bool:
    e = _strip_outer_parens(expr).strip()
    if not e:
        return True
    low = e.lower().replace(" ", "")
    if low in _BOOL_LITERALS:
        return True
    if "meta.revert_taken" in low:
        return True
    # boolean connectors / implication
    if any(tok in low for tok in ("&&", "||", "->")):
        return True
    # comparisons evaluate to boolean
    if any(op in e for op in ("==", "!=", ">=", "<=", ">", "<")):
        return True
    return False


# -----------------------------------------------------------------------------
# Tautology detection (strict)
# -----------------------------------------------------------------------------
def is_tautology(inv: str) -> bool:
    """
    Strict tautology detection. IMPORTANT:
      - Do NOT treat (select(...) >= 0) as tautology. That's "trivial/weak", not tautological.
      - Tautology means identity / always-true by structure (x==x, A->true, A->(x==x)).
    """
    s = _canonicalize(inv)
    if not s:
        return True

    g, rhs = _split_guard(s)
    rhs0 = _strip_outer_parens(rhs).strip()
    low_rhs = rhs0.lower().replace(" ", "")

    # RHS literal true
    if low_rhs == "true":
        return True

    # direct identity compare: X == X
    m = _split_cmp(rhs0)
    if m:
        a, op, b = m
        a0 = _canonicalize(a).replace(" ", "")
        b0 = _canonicalize(b).replace(" ", "")
        if op == "==" and a0 and a0 == b0:
            return True
        # pre.x == pre.x or post.x == post.x (common identity)
        if re.search(r"\b(pre|post)\.([A-Za-z_]\w*)\s*==\s*\1\.\2\b", rhs0):
            return True

    # guard-only forms that reduce to identity:
    #   (G) -> (meta.sender == meta.sender)
    if "metasender==metasender" in low_rhs:
        return True

    # A -> (B == B) already caught by identity, but keep extra defensive:
    if re.search(r"==\s*([A-Za-z0-9_.()]+)\s*$", rhs0):
        # no-op; identity compare already covered
        pass

    return False


# -----------------------------------------------------------------------------
# Trivial/weak detection (broad)
# -----------------------------------------------------------------------------
def is_trivial_weak(inv: str) -> bool:
    """
    Trivial/weak invariants that should NOT guide Flow-2.
    Examples:
      - any >= 0 (often uint non-negativity)
      - meta.sender == meta.sender, meta.origin == meta.origin
      - (anything) -> true
      - pure preconditions (arg.x >= 0) etc.
    """
    s = _canonicalize(inv)
    if not s:
        return True

    _, rhs = _split_guard(s)
    rhs0 = _strip_outer_parens(rhs).strip()
    low = rhs0.lower()

    # implication consequent is true (already covered by tautology, but count as weak too)
    if low.replace(" ", "") == "true":
        return True

    # Identity compares (weak even if not flagged as tautology by some callers)
    if re.match(r"^\s*(.+?)\s*==\s*\1\s*$", rhs0):
        return True

    # >= 0 is trivial/weak (but NOT tautology)
    if re.search(r">=\s*0\b", rhs0):
        return True

    # common no-signal identities
    if re.search(r"\bmeta\.sender\s*==\s*meta\.sender\b", rhs0):
        return True
    if re.search(r"\bmeta\.origin\s*==\s*meta\.origin\b", rhs0):
        return True

    # pure precondition-ish: references arg/meta only, no pre/post/select/store
    low_s = s.lower()
    has_state = ("pre." in low_s) or ("post." in low_s) or ("select(" in low_s) or ("store(" in low_s)
    if not has_state:
        # arg.<x> >= 0  (BV modeling / uint domain) is typically useless
        if re.search(r"\barg\.[A-Za-z_]\w*\s*>=\s*0\b", s):
            return True
        # simple meta-only comparisons are usually not guidance
        if ("arg." in low_s or "meta." in low_s) and any(op in s for op in (">", "<", "==", "!=", ">=", "<=")):
            return True

    return False


# -----------------------------------------------------------------------------
# Security signal check (must-have tokens)
# -----------------------------------------------------------------------------
def has_security_signal(inv: str) -> bool:
    """
    Fast "is this even about something meaningful?" check.
    For refined invariants, require at least one strong token AND avoid pure tautologies.
    """
    s = _canonicalize(inv)
    if not s:
        return False

    low = s.lower()
    if any(tok in low for tok in _SIGNAL_TOKENS):
        return True

    # fallback: if it has both pre and post somewhere, that's signal
    if ("pre." in low or "select(pre." in low) and ("post." in low or "select(post." in low):
        return True

    return False


# -----------------------------------------------------------------------------
# Utility scoring (optional, but useful for bucketing)
# -----------------------------------------------------------------------------
def utility_score(inv: str, fn_name: str = "") -> int:
    """
    Cheap, explainable utility score.
      >=2  => useful guidance
      else => weak/trivial
    """
    s = _canonicalize(inv)
    low = s.lower()
    score = 0

    # +2 if relates pre<->post
    if (("pre." in low or "select(pre." in low) and ("post." in low or "select(post." in low)):
        score += 2

    # +2 if uses arg.* or meta.*
    if "arg." in low or "meta." in low:
        score += 2

    # +1 if implication present
    if "->" in s:
        score += 1

    # -4 tautology
    if is_tautology(s):
        score -= 4

    # -2 trivial weak patterns
    if is_trivial_weak(s):
        score -= 2

    # -1 if it's a no-op transition (pre == post on same scalar)
    # NOTE: do NOT treat raw mapping compares here; those should be discarded earlier in refiners.
    s0 = s.replace(" ", "")
    m = re.match(r"^\(*post\.([A-Za-z_]\w*)\)*==\(*pre\.\1\)*$", s0)
    if m:
        score -= 2

    # extra penalty if function is mutating and invariant is weak/trivial
    if fn_name:
        if any(fn_name.lower().startswith(h) for h in _MUTATING_FN_HINTS) and is_trivial_weak(s):
            score -= 1

    return score


def classify_invariant_quality(inv: str, fn_name: str = "") -> Dict[str, Any]:
    """
    Single-call classifier for agent.py usage.

    Returns:
      {
        "ok_for_guidance": bool,
        "is_tautology": bool,
        "is_trivial": bool,
        "has_signal": bool,
        "score": int,
        "reason": str,
      }
    """
    s = _canonicalize(inv)
    tauto = is_tautology(s)
    triv = is_trivial_weak(s)
    sig = has_security_signal(s)
    sc = utility_score(s, fn_name=fn_name)

    ok = (not tauto) and (not triv) and sig and (sc >= 2)

    if tauto:
        reason = "tautology"
    elif triv:
        reason = "trivial_or_weak"
    elif not sig:
        reason = "no_security_signal"
    elif sc < 2:
        reason = "low_utility_score"
    else:
        reason = "ok"

    return {
        "ok_for_guidance": ok,
        "is_tautology": tauto,
        "is_trivial": triv,
        "has_signal": sig,
        "score": sc,
        "reason": reason,
    }
