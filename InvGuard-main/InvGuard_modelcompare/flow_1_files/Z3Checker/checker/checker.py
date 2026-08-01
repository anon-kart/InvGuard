# checker/checker.py
# Minimal Z3 checker that consumes a SymFunctionModel and compiled invariants.

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Iterable
from z3 import Solver, Not, sat


@dataclass
class CheckOutcome:
    name: str                 # invariant name / message
    status: str               # "HOLDS", "VIOLATED", "UNKNOWN", or "UNVERIFIED_UNSOUND"
    model_slice: Optional[Dict[str, Any]]  # counterexample bindings (when violated)

    # --- NEW: keep a back-pointer to the compiled invariant/spec for refinement ---
    inv_raw: Optional[Any] = None          # CompiledInvariant.raw (InvariantSpec), if provided
    inv_z3: Optional[Any] = None           # the z3 BoolRef for this invariant (optional)

    # --- NEW: optional reason string (used for UNSOUND / UNKNOWN diagnostics) ---
    reason: Optional[str] = None


def _model_to_dict(m) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        for d in m.decls():
            try:
                out[d.name()] = str(m[d])
            except Exception:
                out[d.name()] = "<unprintable>"
    except Exception:
        pass
    return out


def check_one(model, inv_bool, assumptions: Optional[Iterable[Any]] = None) -> CheckOutcome:
    """
    Core check: add 'assumptions' (transition constraints), then refute invariant.
    Returns a CheckOutcome (status + optional counterexample).
    Timeout is read from INVGUARD_Z3_TIMEOUT_SEC env var (default 30s).
    """
    import os
    try:
        timeout_ms = int(float(os.environ.get("INVGUARD_Z3_TIMEOUT_SEC", "30"))) * 1000
    except (ValueError, TypeError):
        timeout_ms = 30000

    s = Solver()
    s.set("timeout", timeout_ms)
    for a in (assumptions or []):
        s.add(a)
    s.add(Not(inv_bool))

    r = s.check()
    if r == sat:
        m = s.model()
        return CheckOutcome(
            name="",
            status="VIOLATED",
            model_slice=_model_to_dict(m),
            inv_raw=None,
            inv_z3=inv_bool,
            reason=None,
        )
    elif str(r) == "unsat":
        return CheckOutcome(
            name="",
            status="HOLDS",
            model_slice=None,
            inv_raw=None,
            inv_z3=inv_bool,
            reason=None,
        )
    else:
        return CheckOutcome(
            name="",
            status="UNKNOWN",
            model_slice=None,
            inv_raw=None,
            inv_z3=inv_bool,
            reason="z3-unknown",
        )


def check_compiled_invariants(model, compiled_invariants) -> List[CheckOutcome]:
    """
    Batch-check a list of CompiledInvariant objects (from InvariantManager.compile_all).

    NEW:
      - attaches inv_raw (InvariantSpec) and inv_z3 (BoolRef) to each outcome,
        so higher layers can run deterministic counterexample-guided refinement
        without guessing which invariant failed.
    """
    results: List[CheckOutcome] = []
    for inv in compiled_invariants:
        outcome = check_one(model, inv.z3_bool, model.assumptions)
        outcome.name = getattr(inv, "name", "") or ""

        # --- NEW: attach raw spec for refinement ---
        try:
            outcome.inv_raw = getattr(inv, "raw", None)
        except Exception:
            outcome.inv_raw = None

        # --- NEW: attach z3 bool (already set by check_one, but keep consistent) ---
        try:
            outcome.inv_z3 = getattr(inv, "z3_bool", None)
        except Exception:
            pass

        results.append(outcome)
    return results


def pretty_print_results(results: List[CheckOutcome]) -> None:
    """
    Simple terminal output helper (robust to UNSOUND/partial result objects).
    """
    print("\n=== Invariant Results ===")
    for r in (results or []):
        status = getattr(r, "status", None) or "UNKNOWN"
        name = getattr(r, "name", None) or "<unknown-invariant>"
        reason = getattr(r, "reason", None)

        if status == "HOLDS":
            tag = "✅ HOLDS"
        elif status == "VIOLATED":
            tag = "❌ VIOLATED"
        elif status == "UNVERIFIED_UNSOUND":
            tag = "⚠️ UNVERIFIED_UNSOUND"
        else:
            tag = "❓ UNKNOWN"

        if reason:
            print(f"- {name}: {tag} ({reason})")
        else:
            print(f"- {name}: {tag}")

        model_slice = getattr(r, "model_slice", None)
        if model_slice and status == "VIOLATED":
            print("  Counterexample:")
            shown = 0
            try:
                for k, v in model_slice.items():
                    print(f"    {k} = {v}")
                    shown += 1
                    if shown >= 30:  # avoid spamming huge models
                        print("    ...")
                        break
            except Exception:
                print("    <unprintable model>")