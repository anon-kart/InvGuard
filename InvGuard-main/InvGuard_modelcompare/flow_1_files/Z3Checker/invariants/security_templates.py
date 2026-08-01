# InvGuard/flow_1_files/Z3Checker/invariants/security_templates.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .invariant_manager import InvariantSpec


# --------------------------------------------------------------------
# Security-template directed refinement
#
# Purpose:
#   When a function includes external value transfer:
#       (bool ok,) = payable(x).call{value: v}("");
#   monotonic weakenings (>=, <=) often become semantically weak.
#   These templates provide "security-shaped" invariants that are:
#     - reviewer-friendly (known patterns)
#     - useful for exploit search + patching
#     - bounded + deterministic (no LLM required)
#
# NOTE:
#   InvariantSpec is assumed to support extra metadata fields as kwargs.
#   If your InvariantSpec only accepts (message, expr), you can keep the
#   same calls below by removing template/params fields and storing them
#   in `message` instead.
# --------------------------------------------------------------------


# ----------------------------
# Lightweight template wrapper
# ----------------------------
def _mk_template(
    template: str,
    params: Optional[Dict[str, Any]] = None,
    message: str = "",
) -> InvariantSpec:
    """
    Produce an InvariantSpec that represents a template rather than a fully
    concrete DSL expression.

    The invariant_manager / translator layer can later expand these into DSL
    invariants (recommended), or you can treat these as "hints" for LLM prompting.
    """
    params = params or {}
    # Most codebases allow extra kwargs on dataclasses; if yours does not,
    # replace with: InvariantSpec(message=..., expr=None) and encode template in message.
    return InvariantSpec(
        message=message or f"[template:{template}]",
        expr=None,
        template=template,     # type: ignore[arg-type]
        params=params,         # type: ignore[arg-type]
    )


# ----------------------------
# External-call detectors (cheap)
# ----------------------------
def has_value_call_in_source(fn_src: str) -> bool:
    """
    Very cheap (string) scan:
      - detects `.call{value: ...}("")` and common whitespace variations.
    """
    if not fn_src:
        return False
    s = fn_src.replace(" ", "")
    # Typical Solidity patterns
    return ".call{value:" in s and ")(" in s or ".call{value:" in s and "}(\"" in s or ".call{value:" in s


def has_any_external_call_in_source(fn_src: str) -> bool:
    """
    Broader scan: catches .call/.delegatecall/.staticcall.
    """
    if not fn_src:
        return False
    s = fn_src.replace(" ", "")
    return ".call{" in s or ".call(" in s or ".delegatecall(" in s or ".staticcall(" in s


# ----------------------------
# Template constructors
# ----------------------------
def make_no_external_before_update_template(
    *,
    map_name: str = "balances",
    key: str = "meta.sender",
    message: str = "",
) -> InvariantSpec:
    """
    Template: "No external call before state update" (Checks-Effects-Interactions).

    For SimpleBank.withdraw, the ideal semantic shape is:
      - state update happens before external call
    but in many real contracts, this is violated.

    We represent it as a template so the manager/translator can map it to
    whatever DSL notion of "external_call_taken" / "call_depth" your checker supports.

    If you later add explicit events in the model (meta.external_call_taken),
    you can expand into a concrete invariant like:
      (meta.external_call_taken == true) -> (post.balances == pre.balances - arg.amount)
    """
    return _mk_template(
        template="NO_EC_BEFORE_UPDATE",
        params={"map": map_name, "key": key},
        message=message or "No external call before balance update (CEI)",
    )


def make_call_depth_limit_template(
    limit: int = 1,
    *,
    message: str = "",
) -> InvariantSpec:
    """
    Template: bound reentrancy / external-call depth.
    Typical reviewer-friendly invariant:
      external_call_depth <= 1

    If your Z3 model exposes something like meta.call_depth, this can become:
      meta.call_depth <= limit

    If not, keep as template for downstream expansion/LLM prompting.
    """
    if limit < 1:
        limit = 1
    return _mk_template(
        template="CALL_DEPTH_LIMIT",
        params={"limit": int(limit)},
        message=message or f"External call depth <= {int(limit)}",
    )


def make_no_reentrant_withdraw_template(
    *,
    message: str = "",
) -> InvariantSpec:
    """
    Template: "No successful reentrant withdraw" (attack-shaped constraint).
    Useful when your source shows an external call + state update after it.
    """
    return _mk_template(
        template="NO_REENTRANT_WITHDRAW",
        params={},
        message=message or "No reentrant withdraw succeeds (reentrancy guard)",
    )


def make_effects_before_interactions_template(
    *,
    message: str = "",
) -> InvariantSpec:
    """
    Template: explicit CEI ordering.
    Kept separate from NO_EC_BEFORE_UPDATE so you can map differently if desired.
    """
    return _mk_template(
        template="CEI_ORDER",
        params={},
        message=message or "Effects-before-interactions ordering holds",
    )


def make_transfer_success_implies_state_update_template(
    *,
    map_name: str = "balances",
    key: str = "meta.sender",
    message: str = "",
) -> InvariantSpec:
    """
    Template: if an external value transfer succeeds, the intended state update holds.
    For SimpleBank.withdraw this corresponds to:
      ok == true  ==>  post.balance == pre.balance - arg.amount
    But 'ok' may not exist in the model. Represent as template.
    """
    return _mk_template(
        template="XFER_OK_IMP_STATE_UPDATE",
        params={"map": map_name, "key": key},
        message=message or "Transfer success implies intended state update",
    )


# ----------------------------
# Bundle helpers
# ----------------------------
def security_templates_for_external_value_call(
    *,
    limit: int = 1,
    map_name: str = "balances",
    key: str = "meta.sender",
) -> List[InvariantSpec]:
    """
    Recommended small bundle when .call{value: ...} is present.
    Keep it SMALL and deterministic.
    """
    return [
        make_no_external_before_update_template(map_name=map_name, key=key),
        make_call_depth_limit_template(limit=limit),
        make_no_reentrant_withdraw_template(),
        make_effects_before_interactions_template(),
        make_transfer_success_implies_state_update_template(map_name=map_name, key=key),
    ]


def security_templates_for_any_external_call(
    *,
    limit: int = 1,
) -> List[InvariantSpec]:
    """
    Minimal bundle when any external call is present (call/delegatecall/staticcall).
    """
    return [
        make_call_depth_limit_template(limit=limit),
        make_effects_before_interactions_template(),
    ]
