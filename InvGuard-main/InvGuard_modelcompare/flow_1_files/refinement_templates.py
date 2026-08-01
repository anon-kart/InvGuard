# flow_1_files/refinement_templates.py
"""
Allowed, template-bounded invariant refinements (Reviewer Point 4).

This module defines a small, auditable library of *syntactic* rewrite templates.
Key properties:
  - deterministic, counterexample-aware (but NOT free-form generation)
  - does not change meaning silently outside a template id
  - logs what template was used + which bindings were applied
  - always ensures (meta.revert_taken == false) guard is present exactly once (top-level)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re

# --- Counterexample value parsing (self-contained; mirrors invariant_rewriter) ---
_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")
_INT_RE = re.compile(r"^-?\d+$")
_BV_RE = re.compile(r"bv(\d+)")


def _ce_int(counterexample: Dict[str, Any], key: str) -> Optional[int]:
    """Best-effort parse of a CE binding into a Python int (int/hex/Z3 bv)."""
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


# -----------------------------
# Small helpers (local, no deps)
# -----------------------------

def _ws_collapse(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _repair_missing_parens(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    diff = s.count("(") - s.count(")")
    if diff > 0:
        s = s + (")" * diff)
    return s


def _split_implication(s: str) -> Tuple[str, str]:
    """
    Returns (guard, rhs). If no implication, guard="" and rhs=s.
    Normalizes '=>' to '->'.
    """
    s = _repair_missing_parens((s or "").strip()).replace("=>", "->")
    if "->" not in s:
        return "", s.strip()
    g, rhs = s.split("->", 1)
    return g.strip(), rhs.strip()


def _ensure_no_revert_guard(guard: str) -> str:
    """
    Ensure meta.revert_taken == false is included in the guard, once.
    """
    g0 = (guard or "").strip()
    if not g0:
        return "(meta.revert_taken == false)"
    low = g0.replace(" ", "").lower()
    if "meta.revert_taken" in low:
        return g0
    return f"((meta.revert_taken == false) && ({g0}))"


def _wrap_top_level(guard: str, rhs: str) -> str:
    """
    Always emit fully-parenthesized implication:
      ((GUARD) -> (RHS))
    And ensure meta.revert_taken == false is in GUARD exactly once.
    """
    g = _ensure_no_revert_guard((guard or "").strip())
    r = _repair_missing_parens((rhs or "").strip().replace("=>", "->"))
    return f"(({g}) -> ({r}))"


def _has_top_revert_guard(inv: str) -> bool:
    s = (inv or "").replace(" ", "").lower()
    return "meta.revert_taken==false" in s and "->" in s


def _is_trivial_or_noop(inv_line: str, fn_name: str = "") -> bool:
    """
    Conservative trivial/no-op filter.
    This duplicates safety in agent.py so templates cannot leak junk if used elsewhere.
    """
    s = (inv_line or "").strip()
    if not s:
        return True
    low = s.replace(" ", "").lower()

    # meta.sender == meta.sender
    if "meta.sender==meta.sender" in low:
        return True
    if "pre.owner==pre.owner" in low:
        return True

    # whole-line X == X
    m = re.match(r"^(.*?)(==)(.*?)$", low)
    if m and m.group(1) == m.group(3):
        return True

    # implication with tautological rhs
    if "->" in low:
        rhs = low.split("->", 1)[1].strip()
        m2 = re.match(r"^\(*(.+?)\)*==\(*\1\)*$", rhs)
        if m2:
            return True

    # uint non-negativity
    if re.search(r"select\(post\.[a-z0-9_]+,.*\)\s*>=\s*0", low):
        return True
    if re.search(r"\bpost\.[a-z0-9_]+\s*>=\s*0\b", low):
        return True

    # post==pre no-op transitions
    if ("select(post." in low and "select(pre." in low and "==" in low):
        t = low.replace("select(post.", "select(X.").replace("select(pre.", "select(X.")
        parts = t.split("==")
        if len(parts) == 2 and parts[0].strip() == parts[1].strip():
            return True

    if ("post." in low and "pre." in low and "==" in low):
        t = low.replace("post.", "X.").replace("pre.", "X.")
        parts = t.split("==")
        if len(parts) == 2 and parts[0].strip() == parts[1].strip():
            return True

    return False


def _infer_sender_map_name(inv: str, which: str = "pre") -> Optional[str]:
    """
    Try to infer mapping var from patterns like:
        select(pre.balances, meta.sender)
        select(post.shares, meta.sender)
    """
    s = inv or ""
    m = re.search(rf"select\s*\(\s*{which}\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)", s)
    return m.group(1) if m else None


# -----------------------------
# Template definitions
# -----------------------------

@dataclass(frozen=True)
class TemplateApplication:
    template_id: str
    before: str
    after: str
    bindings: Dict[str, Any]


@dataclass(frozen=True)
class RewriteTemplate:
    template_id: str
    description: str

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        raise NotImplementedError


class AddNoRevertGuard(RewriteTemplate):
    """
    Add top-level ((meta.revert_taken == false) -> (...))
    Only if not already present.
    """

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        s = _repair_missing_parens(inv or "")
        s = s.replace("=>", "->").strip()
        if not s:
            return None
        if _has_top_revert_guard(s):
            return None
        g, rhs = _split_implication(s)
        out = _wrap_top_level(g, rhs)  # ensure revert guard inside guard
        if _is_trivial_or_noop(out, fn_name=fn_name):
            return None
        return TemplateApplication(self.template_id, inv, out, bindings={})


class GuardOverflowAddValue(RewriteTemplate):
    """
    For patterns:
      select(post.M, sender) == select(pre.M, sender) + meta.value
      select(post.M, sender) == select(pre.M, sender) + arg.<x>

    Add feasibility guard:
      meta.value > 0 && (preBal + meta.value >= preBal)
    or
      arg.x > 0 && (preBal + arg.x >= preBal)
    """

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        s = _repair_missing_parens(inv or "").replace("=>", "->").strip()
        if not s:
            return None

        g0, rhs = _split_implication(s)
        if g0:
            # guard-first template should only apply when unguarded
            return None

        rhs_n = _repair_missing_parens(rhs)

        # meta.value case
        pat_mv = re.compile(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*\+\s*meta\.value\b"
        )
        m = pat_mv.search(rhs_n)
        if m:
            pre_map = m.group(2)
            pre_bal = f"select(pre.{pre_map}, meta.sender)"
            guard = f"((meta.value > 0) && ({pre_bal} + meta.value >= {pre_bal}))"
            out = _wrap_top_level(guard, rhs_n)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(
                self.template_id,
                inv,
                out,
                bindings={"pre_map": pre_map, "guard": guard},
            )

        # arg.<x> case (any arg field)
        pat_arg = re.compile(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*\+\s*(arg\.[A-Za-z_]\w*)\b"
        )
        m2 = pat_arg.search(rhs_n)
        if m2:
            pre_map = m2.group(2)
            argx = m2.group(3)
            pre_bal = f"select(pre.{pre_map}, meta.sender)"
            guard = f"(({argx} > 0) && ({pre_bal} + {argx} >= {pre_bal}))"
            out = _wrap_top_level(guard, rhs_n)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(
                self.template_id,
                inv,
                out,
                bindings={"pre_map": pre_map, "arg": argx, "guard": guard},
            )

        return None


class GuardUnderflowSub(RewriteTemplate):
    """
    For pattern:
      select(post.M,sender) == select(pre.M,sender) - arg.<x>
    Add underflow guard:
      select(pre.M,sender) >= arg.<x>
    """

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        s = _repair_missing_parens(inv or "").replace("=>", "->").strip()
        if not s:
            return None

        g0, rhs = _split_implication(s)
        if g0:
            return None

        rhs_n = _repair_missing_parens(rhs)
        pat = re.compile(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*-\s*(arg\.[A-Za-z_]\w*)\b"
        )
        m = pat.search(rhs_n)
        if not m:
            return None

        pre_map = m.group(2)
        argx = m.group(3)
        pre_bal = f"select(pre.{pre_map}, meta.sender)"
        guard = f"({pre_bal} >= {argx})"
        out = _wrap_top_level(guard, rhs_n)
        if _is_trivial_or_noop(out, fn_name=fn_name):
            return None
        return TemplateApplication(
            self.template_id,
            inv,
            out,
            bindings={"pre_map": pre_map, "arg": argx, "guard": guard},
        )


class WeakenEqToGeMonotonic(RewriteTemplate):
    """
    WEAKEN-SECOND:
    If already guarded, weaken fragile equality into monotonic inequality.

    Examples:
      (G -> select(post.M,s) == select(pre.M,s) + meta.value)
        => (G -> select(post.M,s) >= select(pre.M,s))

      (G -> select(post.M,s) == select(pre.M,s) - arg.x)
        => (G -> select(post.M,s) <= select(pre.M,s))
    """

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        s = _repair_missing_parens(inv or "").replace("=>", "->").strip()
        if not s:
            return None

        g0, rhs = _split_implication(s)
        if not g0:
            # weaken-second needs an existing guard
            return None

        g0 = _ensure_no_revert_guard(g0)
        rhs_n = _repair_missing_parens(rhs)

        # == pre + meta.value  -> >= pre
        pat1 = re.compile(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*\+\s*meta\.value\b"
        )
        m1 = pat1.search(rhs_n)
        if m1:
            pre_map = m1.group(2)
            post_map = m1.group(1)
            new_rhs = f"select(post.{post_map}, meta.sender) >= select(pre.{pre_map}, meta.sender)"
            out = _wrap_top_level(g0, new_rhs)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(
                self.template_id,
                inv,
                out,
                bindings={"pre_map": pre_map, "post_map": post_map, "new_rhs": new_rhs},
            )

        # == pre + arg.x -> >= pre
        pat2 = re.compile(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*\+\s*(arg\.[A-Za-z_]\w*)\b"
        )
        m2 = pat2.search(rhs_n)
        if m2:
            pre_map = m2.group(2)
            post_map = m2.group(1)
            new_rhs = f"select(post.{post_map}, meta.sender) >= select(pre.{pre_map}, meta.sender)"
            out = _wrap_top_level(g0, new_rhs)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(
                self.template_id,
                inv,
                out,
                bindings={"pre_map": pre_map, "post_map": post_map, "arg": m2.group(3), "new_rhs": new_rhs},
            )

        # == pre - arg.x -> <= pre
        pat3 = re.compile(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*==\s*select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*-\s*(arg\.[A-Za-z_]\w*)\b"
        )
        m3 = pat3.search(rhs_n)
        if m3:
            pre_map = m3.group(2)
            post_map = m3.group(1)
            new_rhs = f"select(post.{post_map}, meta.sender) <= select(pre.{pre_map}, meta.sender)"
            out = _wrap_top_level(g0, new_rhs)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(
                self.template_id,
                inv,
                out,
                bindings={"pre_map": pre_map, "post_map": post_map, "arg": m3.group(3), "new_rhs": new_rhs},
            )

        return None


class WeakenStrictToNonStrict(RewriteTemplate):
    """
    WEAKEN-SECOND:
    If guarded and uses strict < or > between pre/post, relax to <= or >=.
    """

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        s = _repair_missing_parens(inv or "").replace("=>", "->").strip()
        if not s:
            return None

        g0, rhs = _split_implication(s)
        if not g0:
            return None

        g0 = _ensure_no_revert_guard(g0)
        rhs_n = _repair_missing_parens(rhs)

        # Replace strict comparisons between select(post.*) and select(pre.*)
        # Keep it conservative: only touch a single operator per apply.
        if "select(" not in rhs_n:
            return None

        # >  -> >=
        if re.search(r"\)\s*>\s*select\s*\(\s*pre\.", rhs_n) or re.search(r"\)\s*>\s*select\s*\(\s*post\.", rhs_n):
            new_rhs = re.sub(r"\s*>\s*", " >= ", rhs_n, count=1)
            out = _wrap_top_level(g0, new_rhs)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(self.template_id, inv, out, bindings={"op": ">", "new_rhs": new_rhs})

        # <  -> <=
        if re.search(r"\)\s*<\s*select\s*\(\s*pre\.", rhs_n) or re.search(r"\)\s*<\s*select\s*\(\s*post\.", rhs_n):
            new_rhs = re.sub(r"\s*<\s*", " <= ", rhs_n, count=1)
            out = _wrap_top_level(g0, new_rhs)
            if _is_trivial_or_noop(out, fn_name=fn_name):
                return None
            return TemplateApplication(self.template_id, inv, out, bindings={"op": "<", "new_rhs": new_rhs})

        return None


class StrengthenMonotonicToConservation(RewriteTemplate):
    """
    STRENGTHEN (Point 4): the rest of the catalogue only WEAKENS invariants
    (adds guards, relaxes bounds). That bias is dangerous for a verifier: a
    too-weak invariant passes Z3 yet fails to catch an exploit. This template
    moves in the opposite direction — it TIGHTENS an over-permissive one-sided
    bound into a conservation equality, but ONLY when the counterexample
    confirms the tighter relation actually holds on the failing trace (so we
    never strengthen on speculation and never introduce a false invariant).

    Trigger: guarded `select(post.M, s) >= select(pre.M, s)` (or `<=`) where the
    CE shows post == pre for that slot — i.e. the monotonic bound is looser than
    the observed behaviour. Proposed: `select(post.M, s) == select(pre.M, s)`.
    The downstream Z3 re-check still has the final say; if the equality does not
    verify, the stronger candidate is simply rejected and the original kept.
    """

    def try_apply(self, inv: str, ce: Dict[str, Any], fn_name: str = "") -> Optional[TemplateApplication]:
        s = _repair_missing_parens(inv or "").replace("=>", "->").strip()
        if not s:
            return None
        g0, rhs = _split_implication(s)
        if not g0:
            return None
        g0 = _ensure_no_revert_guard(g0)
        rhs_n = _repair_missing_parens(rhs)

        m = re.search(
            r"select\s*\(\s*post\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)\s*(>=|<=)\s*"
            r"select\s*\(\s*pre\.([A-Za-z_]\w*)\s*,\s*meta\.sender\s*\)",
            rhs_n, flags=re.I,
        )
        if not m:
            return None

        post_map, _op, pre_map = m.group(1), m.group(2), m.group(3)
        post_key = f"select(post.{post_map}, meta.sender)"
        pre_key = f"select(pre.{pre_map}, meta.sender)"

        # CE-CONFIRMATION: only strengthen if the counterexample shows the two
        # slots equal (the monotonic bound is strictly looser than reality).
        post_v = _ce_int(ce, post_key)
        pre_v = _ce_int(ce, pre_key)
        if post_v is None:
            post_v = _ce_int(ce, f"post.{post_map}")
        if pre_v is None:
            pre_v = _ce_int(ce, f"pre.{pre_map}")
        if post_v is None or pre_v is None or post_v != pre_v:
            return None  # no CE evidence that equality holds → do not strengthen

        new_rhs = f"({post_key} == {pre_key})"
        out = _wrap_top_level(g0, new_rhs)
        if _is_trivial_or_noop(out, fn_name=fn_name):
            return None
        return TemplateApplication(
            self.template_id, inv, out,
            bindings={"from_op": _op, "to_op": "==", "ce_confirmed": True},
        )


# -----------------------------
# Registry + ordering
# -----------------------------

def default_templates() -> List[RewriteTemplate]:
    """
    IMPORTANT ordering:
      1) Guard-first templates (feasibility)
      2) Then weaken-second templates
      3) Finally add missing meta.revert guard (if any)
    """
    return [
        GuardOverflowAddValue(
            template_id="GUARD_OVERFLOW_ADD",
            description="Add feasibility guard for post==pre+{meta.value|arg.x} (overflow-safe, non-zero).",
        ),
        GuardUnderflowSub(
            template_id="GUARD_UNDERFLOW_SUB",
            description="Add feasibility guard for post==pre-arg.x (underflow-safe).",
        ),
        WeakenEqToGeMonotonic(
            template_id="WEAKEN_EQ_TO_MONOTONIC",
            description="Weaken guarded fragile equality into monotonic inequality (>= or <=).",
        ),
        WeakenStrictToNonStrict(
            template_id="WEAKEN_STRICT_TO_NONSTRICT",
            description="Weaken guarded strict inequalities to non-strict (>,< -> >=,<=).",
        ),
        StrengthenMonotonicToConservation(
            template_id="STRENGTHEN_MONOTONIC_TO_CONSERVATION",
            description="Tighten an over-permissive one-sided bound (>=,<=) into a "
                        "conservation equality when the counterexample confirms it "
                        "(the only strengthening template; counters the weaken-only bias).",
        ),
        AddNoRevertGuard(
            template_id="ADD_NO_REVERT_GUARD",
            description="Ensure top-level meta.revert_taken==false guard exists once.",
        ),
    ]