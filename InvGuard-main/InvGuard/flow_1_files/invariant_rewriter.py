# flow_1_files/invariant_rewriter.py

from __future__ import annotations

from typing import Optional, Dict, Any, Tuple, TypedDict
import re


# =============================================================================
# Safety / Z3Checker crash-avoidance helpers
# =============================================================================

_BOOL_LITERALS = {"true", "false"}

_BOOL_OPS = ("&&", "||", "->", "=>")
_BOOL_CMP = ("==", "!=", ">=", "<=", ">", "<")

# Heuristic: tokens/expressions that are numeric-ish in InvGuard DSL
_NUMERIC_HINTS = (
    "select(",
    "arg.",
    "meta.value",
    "pre.",
    "post.",
    "+",
    "-",
    "*",
    "/",
)

# If a rewrite loses all of these, it’s probably not useful for downstream modules.
_SECURITY_SIGNAL_HINTS = (
    "select(pre.",
    "select(post.",
    "pre.",
    "post.",
    "arg.",
    "meta.value",
    "meta.sender",
    "meta.revert_taken",
    "owner",
    "ok",
    "balance",
    "balances",
    "allowance",
    "allowances",
)


def _strip_outer_parens(s: str) -> str:
    s = (s or "").strip()
    while s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip()
        if inner.count("(") != inner.count(")"):
            break
        s = inner
    return s


def _is_boolean_expr(expr: str) -> bool:
    """
    Conservative: treat expression as boolean if it contains boolean connectors
    or looks like a boolean comparison / literal.
    """
    e = _strip_outer_parens(expr).strip()
    if not e:
        return True

    low = e.lower().replace(" ", "")

    # direct boolean literals
    if low in _BOOL_LITERALS:
        return True

    # boolean connectors / implication
    if any(op in low for op in (x.replace(" ", "") for x in _BOOL_OPS)):
        return True

    # explicit meta.revert_taken is boolean in InvGuard DSL
    if "meta.revert_taken" in low:
        return True

    # comparisons always evaluate to boolean
    if any(op in e for op in _BOOL_CMP):
        return True

    return False


def _is_numeric_expr(expr: str) -> bool:
    """
    Numeric-ish heuristic:
    - must NOT be a boolean expression as-a-whole
    - should contain numeric hints (select, arg, pre/post, arithmetic)
    """
    e = _strip_outer_parens(expr).strip()
    if not e:
        return False

    if _is_boolean_expr(e):
        return False

    low = e.lower()
    return any(h in low for h in _NUMERIC_HINTS)


def _repair_missing_parens(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    diff = s.count("(") - s.count(")")
    if diff > 0:
        s = s + (")" * diff)
    return s


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _split_guard(inv: str) -> Tuple[str, str]:
    """
    If inv is '(G) -> RHS' or '(G) => RHS', return (G, RHS).
    Otherwise returns ("", inv).
    """
    s = _repair_missing_parens((inv or "").strip()).replace("=>", "->")
    if "->" not in s:
        return "", s
    g, rhs = s.split("->", 1)
    return g.strip(), rhs.strip()


def _already_guarded(inv: str) -> bool:
    low = (inv or "").replace(" ", "").lower()
    return "meta.revert_taken" in low and ("->" in low or "=>" in low)


def _extract_rhs_only(inv_or_rhs: str) -> str:
    """
    If given a full implication, return RHS. Otherwise return as-is.
    This prevents accidentally nesting implications.
    """
    s = _repair_missing_parens((inv_or_rhs or "").strip()).replace("=>", "->")
    if "->" in s:
        return s.split("->", 1)[1].strip()
    return s.strip()


def _wrap_no_revert_guard_exact_once(existing_guard: str, rhs_only: str) -> str:
    """
    Emit exactly one top-level implication:

      (((meta.revert_taken == false) && (existing_guard)) -> (rhs))

    If existing_guard is empty:
      ((meta.revert_taken == false) -> (rhs))

    Also:
      - If rhs_only accidentally contains an implication, keep only its RHS.
      - Avoid double-adding meta.revert_taken guards.
    """
    rhs_only = _extract_rhs_only(rhs_only)
    rhs_only = _repair_missing_parens(rhs_only)

    g = (existing_guard or "").strip()
    g = _repair_missing_parens(g)

    if g:
        lowg = g.replace(" ", "").lower()
        if "meta.revert_taken" in lowg:
            # guard already contains meta.revert_taken; DO NOT add again
            return f"(({g}) -> ({rhs_only}))"
        return f"(((meta.revert_taken == false) && ({g})) -> ({rhs_only}))"

    return f"((meta.revert_taken == false) -> ({rhs_only}))"


def _is_tautology_like(inv: str) -> bool:
    """
    Drop obvious useless invariants that can become 'verified' after rewrite:
      - X == X
      - (G -> (X == X))
      - pre.foo == pre.foo / meta.sender == meta.sender, etc.
      - Non-negativity on uint-ish state: select(post.*, ...) >= 0
      - ok == true / true == true / false == false
      - post==pre no-op transitions (incl. select forms)
    """
    s = _collapse_ws(_repair_missing_parens(inv))
    if not s:
        return True

    # strip outer implication if present
    if "->" in s.replace("=>", "->"):
        _, rhs = _split_guard(s)
        s = _collapse_ws(_strip_outer_parens(rhs))

    low = s.replace(" ", "").lower()

    # direct "true" is useless
    if low == "true":
        return True

    # ok == true / ok == 1
    if re.search(r"\bok\s*==\s*true\b", s, flags=re.I) or re.search(r"\bok\s*==\s*1\b", s, flags=re.I):
        return True
    if re.search(r"\btrue\s*==\s*true\b", s, flags=re.I) or re.search(r"\bfalse\s*==\s*false\b", s, flags=re.I):
        return True

    # X == X
    m = re.match(r"^(.*?)(==)(.*?)$", low)
    if m and m.group(1) == m.group(3):
        return True

    # pre.x == pre.x / post.x == post.x / meta.x == meta.x
    if re.search(r"\b(pre|post|meta)\.[a-z_]\w*\s*==\s*\1\.[a-z_]\w*\b", s, flags=re.I):
        s0 = re.sub(r"\s+", "", s)
        m2 = re.match(r"^(pre|post|meta)\.([A-Za-z_]\w*)==\1\.\2$", s0)
        if m2:
            return True

    # select(post.map, ...) >= 0 is usually type-trivial for uint models
    if re.search(r"select\s*\(\s*post\.[A-Za-z_]\w*\s*,.*\)\s*>=\s*0\b", s, flags=re.I):
        return True
    if re.search(r"\bpost\.[A-Za-z_]\w*\s*>=\s*0\b", s, flags=re.I):
        return True

    # post == pre no-op transitions (incl. select forms)
    s0 = re.sub(r"\s+", "", s).lower()
    if "select(post." in s0 and "select(pre." in s0 and "==" in s0:
        t = s0.replace("select(post.", "select(X.").replace("select(pre.", "select(X.")
        parts = t.split("==")
        if len(parts) == 2 and parts[0] == parts[1]:
            return True

    if "post." in s0 and "pre." in s0 and "==" in s0:
        t = s0.replace("post.", "X.").replace("pre.", "X.")
        parts = t.split("==")
        if len(parts) == 2 and parts[0] == parts[1]:
            return True

    return False


def _has_security_signal(inv: str) -> bool:
    """
    Require at least one meaningful token survives in the rewrite.
    (Prevents rewrite collapsing into identity / vacuous forms.)
    """
    s = (inv or "").lower()
    return any(tok in s for tok in _SECURITY_SIGNAL_HINTS)


def _rhs_mentions_state(rhs: str) -> bool:
    low = (rhs or "").lower()
    return ("post." in low) or ("pre." in low) or ("select(post." in low) or ("select(pre." in low)


def _is_pure_precondition(rhs: str) -> bool:
    """
    Reject arg/meta-only predicates (not invariants) unless they relate pre/post state.
    E.g. (arg.x > 0) is not an invariant.
    """
    s = (rhs or "").strip()
    if not s:
        return True
    if _rhs_mentions_state(s):
        return False
    low = s.lower()
    if ("arg." in low or "meta." in low) and any(op in low for op in ["==", "!=", ">=", "<=", ">", "<"]):
        return True
    return False


# =============================================================================
# Counterexample value parsing (contract-agnostic)
# =============================================================================

_BV_RE = re.compile(r"\(\s*_?\s*bv(\d+)\s+(\d+)\s*\)", flags=re.I)  # (_ bv10 256) or (bv10 256)
_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")
_INT_RE = re.compile(r"^[+-]?\d+$")


def _ce_int(counterexample: Dict[str, Any], key: str) -> Optional[int]:
    """
    Best-effort parse of a CE binding into a Python int.
    Handles:
      - integers as strings "123"
      - hex strings "0x.."
      - Z3 bitvector strings like "(_ bv10 256)"
    """
    if not isinstance(counterexample, dict):
        return None
    v = counterexample.get(key)
    if v is None:
        return None

    if isinstance(v, bool):
        return int(v)

    if isinstance(v, int):
        return v

    s = str(v).strip()
    if not s:
        return None

    if _HEX_RE.match(s):
        try:
            return int(s, 16)
        except Exception:
            return None

    if _INT_RE.match(s):
        try:
            return int(s, 10)
        except Exception:
            return None

    m = _BV_RE.search(s)
    if m:
        try:
            return int(m.group(1), 10)
        except Exception:
            return None

    return None


# =============================================================================
# Parsing: split (lhs op rhs)
# =============================================================================

def _split_cmp(rhs: str) -> Optional[Tuple[str, str, str]]:
    """
    Return (lhs, op, rhs) for the FIRST occurrence.
    We intentionally keep it simple (InvGuard DSL is fairly flat for these invariants).
    """
    s = (rhs or "").strip()
    for op in ("==", "!=", ">=", "<=", ">", "<"):
        if op in s:
            a, b = s.split(op, 1)
            return a.strip(), op, b.strip()
    return None


def _extract_arg_field(inv: str) -> Optional[str]:
    """
    Return first arg.<field> token found, e.g. "arg.amount" / "arg.value" / "arg.x".
    """
    m = re.search(r"\b(arg\.[A-Za-z_]\w*)\b", inv or "")
    return m.group(1) if m else None


# =============================================================================
# Template actions (deterministic, bounded)
# =============================================================================

class RewriteAction(TypedDict, total=False):
    kind: str  # "DROP" | "KEEP_GUARDED" | "ADD_PRECOND" | "WEAKEN_MONOTONIC"
    guard: str
    rhs: str
    precond: str
    reason: str


def _mk_implies(guard: str, rhs: str) -> Optional[str]:
    """
    Build implication and apply utility gating (drop tautology / no-signal).

    ✅ REQUIRED:
      - Ensure meta.revert_taken == false guard appears exactly once.
      - If rhs accidentally contains implication, keep only RHS.
    """
    g = (guard or "").strip()
    r = (rhs or "").strip()
    g = _repair_missing_parens(g)
    r = _repair_missing_parens(r)
    r = _extract_rhs_only(r)

    if not r:
        return None

    # Never emit arg/meta-only preconditions as "invariants"
    if _is_pure_precondition(r):
        return None

    out = _wrap_no_revert_guard_exact_once(g, r)

    # Utility gate: do not return rewrites that are tautological or low-signal
    if _is_tautology_like(out) or (not _has_security_signal(out)):
        return None
    return out


def _infer_map_name(expr: str, which: str) -> Optional[str]:
    """
    Try to infer map name from select(pre.<map>, meta.sender) / select(post.<map>, meta.sender).
    which: "pre" or "post"
    Returns None if it cannot infer (do NOT hardcode balances).
    """
    m = re.search(
        rf"select\s*\(\s*{which}\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)",
        expr or "",
        flags=re.I,
    )
    return m.group(1) if m else None


def _is_raw_mapping_compare(inv: str) -> bool:
    """
    Discard extensional map compare like:
      pre.X == post.X
      post.X != pre.X

    ✅ REQUIRED (reviewer-aligned):
      - Discard ONLY if X is known to be a mapping via global MAPPING_VARS.
      - Do NOT fall back to hardcoded names like balances/allowance.
    """
    s = (inv or "").strip()
    s0 = re.sub(r"\s+", "", s).replace("=>", "->")

    # match pre.X == post.X or post.X != pre.X with same X
    m = re.match(r"^\(*pre\.([A-Za-z_]\w*)\)*(!=|==)\(*post\.\1\)*$", s0)
    if not m:
        m = re.match(r"^\(*post\.([A-Za-z_]\w*)\)*(!=|==)\(*pre\.\1\)*$", s0)
    if not m:
        return False

    var = m.group(1)

    # if select/store exists, it's not an extensional compare
    low = s0.lower()
    if "select(" in low or "store(" in low:
        return False

    mapping_vars = globals().get("MAPPING_VARS", None)
    if isinstance(mapping_vars, set) and var in mapping_vars:
        return True

    return False


def _contains_or_chain(inv: str) -> bool:
    low = (inv or "").replace(" ", "").lower()
    return ("||" in low) or (" or " in (inv or "").lower())


# =============================================================================
# Main rewriter (template-bounded)
# =============================================================================

def rewrite_invariant(
    inv: str,
    counterexample: Dict[str, Any],
    function_name: str = "",
) -> Optional[str]:
    """
    Deterministic counterexample-guided invariant rewriting.

    The rewrite is TEMPLATE-BOUNDED:
      - Parse (guard, rhs) and (lhs op rhs)
      - Choose an action from a small allowed set
      - Construct final string deterministically

    Safety guarantees:
      - Never emit >= / <= where either side is boolean
      - Never rewrite full implications as free-text
      - Never generate arithmetic over BoolRef
      - Never emit extensional mapping comparisons (mapping-vars aware)
      - Always ensure meta.revert_taken==false guard exactly once
      - Drop OR-chains / disjunction invariants
      - Drop tautologies / no-signal rewrites (prevents useless “verified” outputs)
      - Drop pure preconditions (arg/meta-only) as invariants
    """
    inv = _repair_missing_parens((inv or "").strip())
    if not inv:
        return None

    guard0, rhs0 = _split_guard(inv)
    rhs0 = _repair_missing_parens(rhs0)
    rhs0 = _extract_rhs_only(rhs0)

    # Reject if rhs still contains implication (should not happen now)
    if "->" in rhs0.replace("=>", "->"):
        return None

    low0 = rhs0.replace(" ", "").lower()

    # Hard drop rules (bounded)
    if _contains_or_chain(rhs0):
        return None
    if _is_raw_mapping_compare(rhs0):
        return None

    # Drop if incoming is already tautology-like or pure precondition
    if _is_tautology_like(rhs0):
        return None
    if _is_pure_precondition(rhs0):
        return None

    # Function-aware filtering (keep conservative)
    if function_name == "deposit":
        if ("arg." in rhs0) and ("meta.value" not in rhs0):
            return None
    if function_name == "withdraw":
        if "meta.value" in rhs0:
            return None

    cmp_parts = _split_cmp(rhs0)
    if not cmp_parts:
        # Only keep if it actually talks about state
        if _rhs_mentions_state(rhs0):
            return _mk_implies(guard0, rhs0)
        return None

    lhs, op, rhs = cmp_parts

    # Boolean safety for numeric comparisons
    if op in (">=", "<=", ">", "<"):
        if _is_boolean_expr(lhs) or _is_boolean_expr(rhs):
            return None
        if not (_is_numeric_expr(lhs) and _is_numeric_expr(rhs)):
            return None

    # Equality safety: avoid bool-vs-num mixes
    if op in ("==", "!="):
        if _is_boolean_expr(lhs) != _is_boolean_expr(rhs):
            return None

    action: RewriteAction = {"kind": "KEEP_GUARDED", "guard": guard0, "rhs": rhs0}

    # -------------------------------------------------------------------------
    # PRIMARY PATH: named, auditable templates (Reviewer Point 4).
    # The template catalogue in refinement_templates.py is the formal embodiment
    # of "template-bounded refinement": each template has an explicit template_id
    # and emits logged bindings, so every rewrite is attributable to a named,
    # individually-testable rule rather than ad-hoc regex surgery. We try it
    # FIRST; only if no template fires (or its output fails the same downstream
    # validators) do we fall back to the inline action logic below. This keeps
    # the catalogue on the live path (no dead code) while preserving every
    # existing safety guarantee, since template output is re-validated here.
    # -------------------------------------------------------------------------
    try:
        from refinement_templates import default_templates as _default_templates  # local import avoids cycles
        _ce = counterexample if isinstance(counterexample, dict) else {}
        for _tpl in _default_templates():
            try:
                _app = _tpl.try_apply(inv, _ce, fn_name=function_name or "")
            except Exception:
                _app = None
            if not _app or not getattr(_app, "after", None):
                continue
            _cand = _repair_missing_parens(_app.after.strip())
            # Re-validate template output against the SAME guarantees used for
            # inline rewrites. Rather than trust the template's own parenthes
            # nesting (which can be uneven), extract the core comparison and let
            # _mk_implies rebuild a single, balanced guarded implication.
            _g, _r = _split_guard(_cand)
            _r = _extract_rhs_only(_repair_missing_parens(_r))
            _cmp = _split_cmp(_strip_outer_parens(_r))
            if _cmp:
                _lhs, _o, _rh = _cmp
                # Operands can carry stray parens if the template's nesting is
                # uneven; balance each operand independently before rebuilding so
                # the final implication is always well-formed.
                _lhs = _strip_outer_parens(_lhs.strip())
                _rh = _strip_outer_parens(_rh.strip())
                while _lhs.count("(") < _lhs.count(")") and _lhs.endswith(")"):
                    _lhs = _lhs[:-1].strip()
                while _lhs.count("(") > _lhs.count(")") and _lhs.startswith("("):
                    _lhs = _lhs[1:].strip()
                while _rh.count("(") < _rh.count(")") and _rh.endswith(")"):
                    _rh = _rh[:-1].strip()
                while _rh.count("(") > _rh.count(")") and _rh.startswith("("):
                    _rh = _rh[1:].strip()
                _r = f"{_lhs} {_o} {_rh}"
            else:
                _r = _strip_outer_parens(_r)
            if not _r or _is_tautology_like(_r) or _is_pure_precondition(_r):
                continue
            if not _rhs_mentions_state(_r):
                continue
            # Use the canonical revert guard; _mk_implies enforces exactly-once.
            _out = _mk_implies("(meta.revert_taken == false)", _r)
            if _out:
                try:
                    import logging as _tlog
                    _tlog.getLogger(__name__).info(
                        "[det-refine] template=%s applied; bindings=%s",
                        _app.template_id, getattr(_app, "bindings", {}),
                    )
                except Exception:
                    pass
                return _out
    except Exception:
        # Any catalogue problem must never break refinement: fall through to inline.
        pass

    rhs_low = rhs.replace(" ", "").lower()
    lhs_low = lhs.replace(" ", "").lower()

    # -------------------------------------------------------------------------
    # TEMPLATE: ADD_PRECOND (withdraw underflow feasibility), generalized arg.<x>
    # Form: select(post.M, sender) == select(pre.M, sender) - arg.X
    # Add precondition: select(pre.M, sender) >= arg.X
    #
    # CE-GUIDED: Read actual CE values to confirm underflow is the cause.
    # If CE shows pre_balance < amount, underflow is confirmed — add guard.
    # If CE is absent, conservatively add guard anyway (safe).
    # -------------------------------------------------------------------------
    if action["kind"] == "KEEP_GUARDED":
        m_sub = re.search(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*-\s*(arg\.[A-Za-z_]\w*)\b",
            rhs0,
            flags=re.I,
        )
        if m_sub:
            pre_map = m_sub.group(2)
            argx = m_sub.group(3)
            pre_bal_key = f"select(pre.{pre_map}, meta.sender)"
            precond = f"({pre_bal_key} >= {argx})"

            # CE-GUIDED: read actual values to confirm underflow is the failure mode
            pre_v = _ce_int(counterexample, pre_bal_key)
            # also try flat key form used by Z3 (e.g. "pre.balances" or argx without prefix)
            if pre_v is None:
                pre_v = _ce_int(counterexample, f"pre.{pre_map}")
            amt_v = _ce_int(counterexample, argx)
            if amt_v is None:
                # try without "arg." prefix
                plain_key = argx.replace("arg.", "", 1)
                amt_v = _ce_int(counterexample, plain_key)
                if amt_v is None:
                    amt_v = _ce_int(counterexample, f"arg.{plain_key}")

            # CE-GUIDED policy (Point 4): only add the precondition when the
            # counterexample CONFIRMS underflow (pre < amt). Previously we added
            # the guard even when CE values were unknown ("conservative"), but
            # that weakens an invariant on speculation and can manufacture
            # vacuous/over-guarded invariants. For a soundness-focused tool it is
            # better to make NO change than an unjustified weakening: leave the
            # invariant as-is and let it be re-checked. Unknown values therefore
            # no longer trigger a rewrite.
            _underflow_confirmed = (pre_v is not None and amt_v is not None and pre_v < amt_v)
            if _underflow_confirmed:
                action = {
                    "kind": "ADD_PRECOND",
                    "guard": guard0,
                    "rhs": rhs0,
                    "precond": precond,
                    "reason": "underflow-feasibility(CE-confirmed)",
                }

    # -------------------------------------------------------------------------
    # TEMPLATE: ADD_PRECOND (overflow feasibility), generalized arg.<x>
    # Equality with + meta.value or + arg.X => add monotonic overflow guard
    #
    # CE-GUIDED: Check if CE shows post.value > pre.value (overflow direction).
    # -------------------------------------------------------------------------
    if action["kind"] == "KEEP_GUARDED" and op == "==":
        # + meta.value
        if re.search(r"\+\s*meta\.value\b", rhs0, flags=re.I):
            pre_map = _infer_map_name(rhs0, "pre")
            if pre_map:
                x = f"select(pre.{pre_map}, meta.sender)"
                # CE-GUIDED: read meta.value from CE to confirm it's positive
                meta_v = _ce_int(counterexample, "meta.value")
                # Point 4: add the overflow guard ONLY when the CE confirms the
                # overflow direction (meta.value strictly positive). Unknown or
                # zero value → no speculative guard.
                if meta_v is not None and meta_v > 0:
                    precond = f"((meta.value > 0) && ({x} + meta.value >= {x}))"
                    action = {
                        "kind": "ADD_PRECOND",
                        "guard": guard0,
                        "rhs": rhs0,
                        "precond": precond,
                        "reason": "overflow-feasibility(meta.value, CE-confirmed)",
                    }
            else:
                return None
        else:
            # + arg.<x>
            m_add = re.search(r"\+\s*(arg\.[A-Za-z_]\w*)\b", rhs0, flags=re.I)
            if m_add:
                argx = m_add.group(1)
                pre_map = _infer_map_name(rhs0, "pre")
                if pre_map:
                    x = f"select(pre.{pre_map}, meta.sender)"
                    # CE-GUIDED: confirm argx is positive in CE
                    arg_v = _ce_int(counterexample, argx)
                    if arg_v is None:
                        arg_v = _ce_int(counterexample, argx.replace("arg.", "", 1))
                    # Point 4: only add when CE confirms arg strictly positive.
                    if arg_v is not None and arg_v > 0:
                        precond = f"(({argx} > 0) && ({x} + {argx} >= {x}))"
                        action = {
                            "kind": "ADD_PRECOND",
                            "guard": guard0,
                            "rhs": rhs0,
                            "precond": precond,
                            "reason": "overflow-feasibility(arg, CE-confirmed)",
                        }
                else:
                    return None

    # -------------------------------------------------------------------------
    # TEMPLATE: WEAKEN_MONOTONIC (CE-guided direction), generalized
    # Equality across pre/post often fails; monotonic inequality is more stable.
    #
    # CE-GUIDED: Read actual post/pre values from CE to decide direction.
    #   If CE shows post.map > pre.map → balance grew → deposit pattern → >=
    #   If CE shows post.map < pre.map → balance shrank → withdraw pattern → <=
    #   Fall back to syntactic heuristic if CE values unavailable.
    # -------------------------------------------------------------------------
    if action["kind"] == "KEEP_GUARDED" and op == "==" and ("select(post." in lhs_low and "select(pre." in rhs_low):
        post_map = _infer_map_name(lhs, "post")
        pre_map = _infer_map_name(rhs, "pre")
        if not post_map or not pre_map:
            return None

        post_bal = f"select(post.{post_map}, meta.sender)"
        pre_bal = f"select(pre.{pre_map}, meta.sender)"

        # CE-GUIDED direction: read actual values from Z3 counterexample
        post_v = _ce_int(counterexample, post_bal)
        if post_v is None:
            post_v = _ce_int(counterexample, f"post.{post_map}")
        pre_v = _ce_int(counterexample, pre_bal)
        if pre_v is None:
            pre_v = _ce_int(counterexample, f"pre.{pre_map}")

        direction = None
        if post_v is not None and pre_v is not None:
            # CE tells us exactly what happened
            if post_v > pre_v:
                direction = ">="   # balance grew in CE → invariant wants >=
            elif post_v < pre_v:
                direction = "<="   # balance shrank in CE → invariant wants <=
            # if equal, fall through to syntactic heuristic
        
        # Syntactic heuristic as fallback when CE values are unavailable
        if direction is None:
            if re.search(r"\+\s*meta\.value\b", rhs0, flags=re.I) or re.search(r"\+\s*arg\.[A-Za-z_]\w*\b", rhs0, flags=re.I):
                direction = ">="
            if re.search(r"-\s*arg\.[A-Za-z_]\w*\b", rhs0, flags=re.I):
                direction = "<="

        if direction is None:
            if function_name == "withdraw":
                direction = "<="
            elif function_name == "deposit":
                direction = ">="

        if direction in (">=", "<="):
            action = {
                "kind": "WEAKEN_MONOTONIC",
                "guard": guard0,
                "rhs": f"{post_bal} {direction} {pre_bal}",
                "reason": f"weaken-eq-to-monotonic(CE-guided={post_v is not None and pre_v is not None})",
            }

    # -------------------------------------------------------------------------
    # TEMPLATE: STRENGTHEN_TO_CONSERVATION (Point 4 — the only strengthening rule)
    # The rest of the catalogue only weakens. A too-weak invariant passes Z3 yet
    # misses exploits, so we add a tightening direction: when the invariant is an
    # over-permissive one-sided bound select(post.M,s) >= / <= select(pre.M,s)
    # AND the counterexample CONFIRMS the two slots are equal (the bound is
    # strictly looser than observed behaviour), tighten to a conservation
    # equality. CE-confirmed only — never speculative; Z3 re-check still decides.
    # -------------------------------------------------------------------------
    if action["kind"] == "KEEP_GUARDED":
        m_mono = re.search(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*(>=|<=)\s*"
            r"select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)",
            rhs0, flags=re.I,
        )
        if m_mono:
            _pm, _op2, _prm = m_mono.group(1), m_mono.group(2), m_mono.group(3)
            _pk = f"select(post.{_pm}, meta.sender)"
            _rk = f"select(pre.{_prm}, meta.sender)"
            _pv = _ce_int(counterexample, _pk)
            if _pv is None:
                _pv = _ce_int(counterexample, f"post.{_pm}")
            _rv = _ce_int(counterexample, _rk)
            if _rv is None:
                _rv = _ce_int(counterexample, f"pre.{_prm}")
            if _pv is not None and _rv is not None and _pv == _rv:
                action = {
                    "kind": "WEAKEN_MONOTONIC",  # reuse equality-emitting applier
                    "guard": guard0,
                    "rhs": f"{_pk} == {_rk}",
                    "reason": "strengthen-monotonic-to-conservation(CE-confirmed)",
                }

    # -------------------------------------------------------------------------
    # TEMPLATE: KEEP_GUARDED (default)
    # If it touches state, wrap with revert guard (and preserve any existing guard)
    # -------------------------------------------------------------------------
    if action["kind"] == "KEEP_GUARDED":
        if _rhs_mentions_state(rhs0):
            return _mk_implies(guard0, rhs0)
        return None

    # -------------------------------------------------------------------------
    # Apply action deterministically (and utility gate inside _mk_implies)
    # -------------------------------------------------------------------------
    if action["kind"] == "DROP":
        return None

    if action["kind"] == "WEAKEN_MONOTONIC":
        return _mk_implies(action.get("guard", ""), action.get("rhs", ""))

    if action["kind"] == "ADD_PRECOND":
        g = action.get("guard", "")
        precond = action.get("precond", "")
        rhs_final = action.get("rhs", "")

        if not precond:
            return None

        if g:
            new_g = f"(({g}) && ({precond}))"
        else:
            new_g = precond

        return _mk_implies(new_g, rhs_final)

    return None