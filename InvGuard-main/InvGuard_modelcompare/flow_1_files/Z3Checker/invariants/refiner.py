# InvGuard/flow_1_files/Z3Checker/invariants/refiner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .invariant_manager import InvariantSpec

# ✅ NEW (Step 4): security templates
from .security_templates import (
    has_value_call_in_source,
    has_any_external_call_in_source,
    security_templates_for_external_value_call,
    security_templates_for_any_external_call,
)

# ----------------------------
# Rewrite operator identifiers
# ----------------------------
OPS = {
    "WEAKEN_EQ_TO_GE",
    "WEAKEN_EQ_TO_LE",
    "ADD_GUARD",                 # implies(guard, inv)
    "ADD_REQUIRE_PRECONDITION",  # implies(require-like precondition, inv)
    "ADD_SECURITY_TEMPLATE",     # add security-shaped template candidates
    "DROP_RIGHT_CONJ",           # (A and B) -> A or B
}

@dataclass
class RefinementStep:
    op: str
    before: InvariantSpec
    after: InvariantSpec
    note: str

def _is_dict(node): return isinstance(node, dict)
def _op(node): return (node.get("op") or "").lower() if _is_dict(node) else ""

def _mk(op: str, args: List[Any]) -> Dict[str, Any]:
    return {"op": op, "args": args}

def _wrap_guard(inv_expr: Dict[str, Any], guard_expr: Dict[str, Any]) -> Dict[str, Any]:
    return _mk("implies", [guard_expr, inv_expr])

def _weaken_eq(expr: Dict[str, Any], to_op: str) -> Optional[Dict[str, Any]]:
    if not _is_dict(expr) or _op(expr) != "==":
        return None
    a, b = expr["args"][0], expr["args"][1]
    return _mk(to_op, [a, b])  # ">=" or "<="

def _drop_conj(expr: Dict[str, Any], keep_left: bool) -> Optional[Dict[str, Any]]:
    if not _is_dict(expr) or _op(expr) != "and":
        return None
    args = expr.get("args", [])
    if len(args) < 2:
        return None
    return args[0] if keep_left else args[1]

def _extract_simple_guard_candidates(model_slice: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Heuristic guard candidates derived from counterexample bindings.
    Keep it SMALL & safe: reviewers want bounded, not perfect.
    """
    guards = []

    # If meta.value exists, add meta.value > 0
    if any(k.endswith("meta.value") or k == "meta.value" for k in model_slice.keys()):
        guards.append(_mk(">", ["meta.value", 0]))

    # Guard against self-transfer: arg.to != meta.sender
    if ("arg.to" in model_slice or any(k.endswith("arg.to") for k in model_slice.keys())):
        guards.append(_mk("!=", ["arg.to", "meta.sender"]))

    # If you see revert_taken in the model, allow success-only guard:
    if "meta.revert_taken" in model_slice:
        guards.append(_mk("not", ["meta.revert_taken"]))

    # Dedup (by string)
    seen = set()
    out = []
    for g in guards:
        s = str(g)
        if s not in seen:
            seen.add(s)
            out.append(g)
    return out


# ----------------------------
# NEW: require-aware semantic refinement (balance deltas)
# ----------------------------
def _contains_tokens(expr: Any, tokens: List[str]) -> bool:
    """
    Best-effort token presence check over the AST.
    Handles nested dict/list structures and leaf strings.
    """
    if expr is None:
        return False
    if isinstance(expr, str):
        s = expr
        return any(t in s for t in tokens)
    if isinstance(expr, (int, float, bool)):
        return False
    if isinstance(expr, list):
        return any(_contains_tokens(x, tokens) for x in expr)
    if isinstance(expr, dict):
        if _contains_tokens(expr.get("op"), tokens):
            return True
        return _contains_tokens(expr.get("args", []), tokens)
    return False

def _is_select(node: Any, state_prefix: str, map_name: str = "balances") -> bool:
    """
    Match select(pre.balances, meta.sender) or select(post.balances, meta.sender)
    in the AST form: {"op":"select","args":[<map>, <key>]}.
    """
    if not _is_dict(node) or _op(node) != "select":
        return False
    args = node.get("args", [])
    if len(args) != 2:
        return False

    m, k = args[0], args[1]
    want_map = f"{state_prefix}.{map_name}"
    return (m == want_map) and (k == "meta.sender")

def _mk_pre_balance(map_name: str = "balances") -> Dict[str, Any]:
    return _mk("select", [f"pre.{map_name}", "meta.sender"])

def _mk_post_balance(map_name: str = "balances") -> Dict[str, Any]:
    return _mk("select", [f"post.{map_name}", "meta.sender"])

def _mk_and(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    # Avoid deep nesting for simple 2-guard combos.
    return _mk("and", [a, b])

def _find_delta_equality(expr: Any, amount_vars: List[str]) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Try to find an equality of the form:
      select(post.balances, meta.sender) == select(pre.balances, meta.sender) +/- AMOUNT
    inside expr.

    Returns: (eq_node, amount_var_used) if found.
    """
    if not _is_dict(expr):
        return None

    op = _op(expr)

    # Direct match
    if op == "==":
        args = expr.get("args", [])
        if len(args) != 2:
            return None
        lhs, rhs = args[0], args[1]

        if not _is_select(lhs, "post", "balances"):
            return None
        if not _is_dict(rhs):
            return None
        rop = _op(rhs)
        if rop not in {"+", "-"}:
            return None
        rargs = rhs.get("args", [])
        if len(rargs) != 2:
            return None
        a0, a1 = rargs[0], rargs[1]
        if not _is_select(a0, "pre", "balances"):
            return None
        if a1 not in amount_vars:
            return None
        return (expr, a1)

    # Search inside implies / and / or
    for sub in expr.get("args", []) or []:
        hit = _find_delta_equality(sub, amount_vars)
        if hit:
            return hit

    return None

def _require_guard_for_delta(eq_expr: Dict[str, Any], amount_var: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Given a delta equality node, compute a require-like guard.
    """
    if not _is_dict(eq_expr) or _op(eq_expr) != "==":
        return None

    lhs, rhs = eq_expr.get("args", [None, None])[0], eq_expr.get("args", [None, None])[1]
    if lhs is None or rhs is None or not _is_dict(rhs):
        return None

    rop = _op(rhs)
    if rop not in {"+", "-"}:
        return None

    rargs = rhs.get("args", [])
    if len(rargs) != 2:
        return None
    a0, a1 = rargs[0], rargs[1]
    if not _is_select(a0, "pre", "balances"):
        return None
    if a1 != amount_var:
        return None

    pre_bal = _mk_pre_balance("balances")

    if rop == "-":
        guard = _mk(">=", [pre_bal, amount_var])
        return guard, f"require(pre_balance >= {amount_var})"

    # rop == "+"
    # keep bounded and safe: require(amount > 0) AND overflow-feasible (pre+amount >= pre)
    sum_expr = _mk("+", [pre_bal, amount_var])
    g1 = _mk(">", [amount_var, 0])
    g2 = _mk(">=", [sum_expr, pre_bal])
    guard = _mk("and", [g1, g2])
    return guard, f"require({amount_var} > 0 && pre_balance+{amount_var}>=pre_balance)"

def _inject_semantic_delta(expr: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Handle common wrappers:
      - implies(success_guard, eq_delta)
      - or(eq_delta, amount==0)
      - nested forms

    Output candidate is always an implication:
      implies( (success_guard AND require_guard), eq_delta )

    If we cannot find eq_delta, returns None.
    """
    amount_vars = ["arg.amount", "meta.value"]

    hit = _find_delta_equality(expr, amount_vars)
    if not hit:
        return None
    eq_node, amount_var = hit

    rg = _require_guard_for_delta(eq_node, amount_var)
    if not rg:
        return None
    req_guard, note = rg

    # If top-level is implies(guard, body), combine the guards.
    if _op(expr) == "implies":
        args = expr.get("args", [])
        if len(args) == 2 and _is_dict(args[0]):
            success_guard = args[0]
            combined = _mk_and(success_guard, req_guard)
            return _mk("implies", [combined, eq_node]), f"{note} (inside success-guard)"

    # Otherwise: just output implies(req_guard, eq_node)
    return _mk("implies", [req_guard, eq_node]), f"{note} (extracted delta branch)"


# ----------------------------
# ✅ NEW (Step 4): external-call awareness hook
# ----------------------------
def _best_effort_get_function_source(counterexample: Dict[str, Any]) -> str:
    """
    Your pipeline may store function source in different keys.
    We accept any of these (whichever exists):
      - counterexample["function_source"]
      - counterexample["fn_src"]
      - counterexample["source"]
      - counterexample["notes"] (if it contains Solidity snippet)
    """
    if not isinstance(counterexample, dict):
        return ""
    for k in ("function_source", "fn_src", "source", "notes"):
        v = counterexample.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""

def _external_call_present(counterexample: Dict[str, Any]) -> Tuple[bool, bool, str]:
    """
    Returns:
      (has_value_call, has_any_external_call, src_snippet_used)
    """
    src = _best_effort_get_function_source(counterexample)
    if not src:
        return (False, False, "")

    hv = bool(has_value_call_in_source(src))
    ha = bool(has_any_external_call_in_source(src))
    return (hv, ha, src)


def refine_one(
    spec: InvariantSpec,
    counterexample: Dict[str, str],
    max_candidates: int = 6
) -> Tuple[List[InvariantSpec], List[RefinementStep]]:
    """
    Deterministically generate a SMALL set of refined candidates.
    No LLM needed. This is what convinces reviewers it's operational.
    """
    if not spec.expr:
        return [], []

    expr = spec.expr
    candidates: List[InvariantSpec] = []
    steps: List[RefinementStep] = []

    # R1/R2: weaken equality
    ge = _weaken_eq(expr, ">=")
    if ge:
        s2 = InvariantSpec(message=(spec.message or "") + " [ref:==->>=]", expr=ge)
        candidates.append(s2)
        steps.append(RefinementStep("WEAKEN_EQ_TO_GE", spec, s2, "Weakened == to >="))

    le = _weaken_eq(expr, "<=")
    if le:
        s2 = InvariantSpec(message=(spec.message or "") + " [ref:==-><=]", expr=le)
        candidates.append(s2)
        steps.append(RefinementStep("WEAKEN_EQ_TO_LE", spec, s2, "Weakened == to <="))

    # ---------------------------------------------------------
    # ✅ FIXED: require-aware semantic invariants (delta exact)
    #
    # Previously: only worked when expr.op == "=="
    # Now: works through implies(...) and or(...)
    # Also: supports arg.amount OR meta.value
    # ---------------------------------------------------------
    try:
        if _contains_tokens(expr, ["pre.balances", "post.balances"]) and _contains_tokens(expr, ["arg.amount", "meta.value"]):
            injected = _inject_semantic_delta(expr)
            if injected:
                guarded_expr, note = injected
                s2 = InvariantSpec(message=(spec.message or "") + " [ref:req-guard]", expr=guarded_expr)
                candidates.append(s2)
                steps.append(
                    RefinementStep(
                        "ADD_REQUIRE_PRECONDITION",
                        spec,
                        s2,
                        f"Injected require-like precondition: {note}",
                    )
                )
    except Exception:
        pass

    # ---------------------------------------------------------
    # ✅ NEW (Step 4): security-template directed refinement
    # ---------------------------------------------------------
    try:
        has_val_call, has_any_call, _src = _external_call_present(counterexample)
        tmpl_specs: List[InvariantSpec] = []
        if has_val_call:
            tmpl_specs = security_templates_for_external_value_call(limit=1, map_name="balances", key="meta.sender")
        elif has_any_call:
            tmpl_specs = security_templates_for_any_external_call(limit=1)

        for ts in tmpl_specs:
            ts2 = InvariantSpec(
                message=(ts.message or "") + " [ref:sec-template]",
                expr=getattr(ts, "expr", None),
                template=getattr(ts, "template", None),  # type: ignore[arg-type]
                params=getattr(ts, "params", None),      # type: ignore[arg-type]
            )
            candidates.append(ts2)
            steps.append(
                RefinementStep(
                    "ADD_SECURITY_TEMPLATE",
                    spec,
                    ts2,
                    f"Added security template candidate: {getattr(ts, 'template', 'UNKNOWN')}",
                )
            )
    except Exception:
        pass

    # R3: add guard (implies)
    for g in _extract_simple_guard_candidates(counterexample):
        guarded = _wrap_guard(expr, g)
        s2 = InvariantSpec(message=(spec.message or "") + " [ref:guard]", expr=guarded)
        candidates.append(s2)
        steps.append(RefinementStep("ADD_GUARD", spec, s2, f"Added guard {g}"))

    # R4: drop conjunct (only if 'and')
    left = _drop_conj(expr, keep_left=True)
    if left:
        s2 = InvariantSpec(message=(spec.message or "") + " [ref:drop-right]", expr=left)
        candidates.append(s2)
        steps.append(RefinementStep("DROP_RIGHT_CONJ", spec, s2, "Dropped RHS conjunct"))
    right = _drop_conj(expr, keep_left=False)
    if right:
        s2 = InvariantSpec(message=(spec.message or "") + " [ref:drop-left]", expr=right)
        candidates.append(s2)
        steps.append(RefinementStep("DROP_RIGHT_CONJ", spec, s2, "Dropped LHS conjunct"))

    return candidates[:max_candidates], steps[:max_candidates]
