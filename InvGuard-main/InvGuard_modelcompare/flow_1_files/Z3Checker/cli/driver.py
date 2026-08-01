# cli/driver.py

import argparse
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

from invariants.invariant_manager import InvariantManager, InvariantSpec, CompiledInvariant
from parser.solidity_parser import SolidityParser
from model.symmodel_builder import SymModelBuilder
from checker.checker import check_compiled_invariants, pretty_print_results

# ===========================
# Counterexample-guided refinement
# ===========================
# This module is optional. If present, it must expose:
#   rewrite_specs(specs: List[InvariantSpec], results, model) -> Tuple[List[InvariantSpec], dict]
try:
    from invariants.invariant_rewriter import rewrite_specs
except Exception:
    rewrite_specs = None


# ----------------------------
# Result wrappers
# ----------------------------
@dataclass
class _UnsoundResult:
    """
    Minimal result object compatible with checker.pretty_print_results()
    and adapter parsing.

    Used when the function/model is not soundly modeled, so solver output
    must not be treated as evidence.
    """
    name: str
    status: str = "UNVERIFIED_UNSOUND"
    reason: str = "unsound model"
    model_slice: Optional[Dict[str, Any]] = None


@dataclass
class _RejectedResult:
    """
    Per-invariant compile/encode/translation failure.

    This prevents a single unsupported invariant from crashing the whole run,
    while ensuring unsupported invariants are excluded from verified output.
    """
    name: str
    status: str = "REJECTED_UNSUPPORTED"
    reason: str = "compile failed"
    model_slice: Optional[Dict[str, Any]] = None


# ----------------------------
# Input cleanup
# ----------------------------
def _repair_missing_parens_line(s: str) -> str:
    """
    Repair invariants missing closing parentheses.
    We only ever add ')' to the end; we never reorder.
    """
    s = (s or "").strip()

    if not s:
        return s

    diff = s.count("(") - s.count(")")

    if diff > 0:
        s = s + (")" * diff)

    return s


def _load_llm_invariants_lines(path: str) -> List[str]:
    """
    Load LLM invariants as cleaned lines.

    This preserves line identity so rejected translator lines can be emitted
    as JSONL results and traced by the adapter.
    """
    lines_out: List[str] = []

    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.rstrip("\n")

            if not s.strip():
                continue

            st = s.strip()

            if st.startswith("```"):
                continue

            if st.endswith(";"):
                st = st[:-1].strip()

            st = _repair_missing_parens_line(st)

            if st:
                lines_out.append(st)

    return lines_out


def _load_llm_invariants_text(path: str) -> str:
    """
    Load LLM invariants text with minimal cleanup + parenthesis repair.
    """
    lines_out = _load_llm_invariants_lines(path)
    return "\n".join(lines_out) + ("\n" if lines_out else "")


# ----------------------------
# JSONL result emission
# ----------------------------
def _result_status(r: Any) -> str:
    return str(getattr(r, "status", "") or "")


def _result_name(r: Any) -> str:
    return str(getattr(r, "name", "") or "<invariant>")


def _result_reason(r: Any) -> str:
    return str(getattr(r, "reason", "") or "")


def _result_model(r: Any) -> Dict[str, str]:
    """
    Convert checker model/counterexample slice to a JSON-safe dict.
    """
    raw = getattr(r, "model_slice", None)

    if raw is None:
        raw = getattr(r, "model", None)

    if not isinstance(raw, dict):
        return {}

    return {str(k): str(v) for k, v in raw.items()}


def _emit_json_result(
    idx: int,
    inv: str,
    status: str,
    reason: str = "",
    model: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit one schema-stable JSON object per invariant.

    The adapter consumes these lines instead of scraping human text.
    """
    obj = {
        "idx": idx,
        "inv": inv,
        "status": status,
    }

    if reason:
        obj["reason"] = reason

    if model:
        obj["model"] = {str(k): str(v) for k, v in model.items()}

    print(json.dumps(obj, sort_keys=True))


def _emit_json_results_from_objects(results: List[Any]) -> None:
    """
    Emit JSONL from checker/rejected/unsound result objects.
    """
    for i, r in enumerate(results, start=1):
        _emit_json_result(
            idx=i,
            inv=_result_name(r),
            status=_result_status(r),
            reason=_result_reason(r),
            model=_result_model(r),
        )


def _emit_json_rejected_lines(
    raw_lines: List[str],
    reason: str,
    start_idx: int = 1,
) -> None:
    """
    Emit every raw LLM invariant as rejected.

    Used in fail-closed mode when translation accepts zero invariants.
    """
    for offset, line in enumerate(raw_lines):
        _emit_json_result(
            idx=start_idx + offset,
            inv=line,
            status="REJECTED_UNSUPPORTED",
            reason=reason,
        )

def _attach_original_lines_to_specs(
    specs: List[InvariantSpec],
    raw_lines: List[str],
) -> List[InvariantSpec]:
    """
    Preserve the original LLM invariant text on each accepted InvariantSpec.

    Why:
      The translator may set sp.message to labels like inv_1/inv_2.
      If we use those labels as CompiledInvariant.name, JSON output loses the
      actual invariant formula and downstream Flow-1 writes inv_2 instead of:
        (meta.revert_taken == false) -> (post.feeBps == pre.feeBps)

    Assumption:
      translate_lines_to_specs preserves accepted invariant order.
    """
    usable_raw = [ln.strip() for ln in (raw_lines or []) if ln and ln.strip()]

    for i, sp in enumerate(specs or []):
        if i < len(usable_raw):
            try:
                setattr(sp, "source_line", usable_raw[i])
            except Exception:
                pass

    return specs

# ----------------------------
# Function/model soundness checks
# ----------------------------
def _find_function_ir(cir, fn_name: str):
    for f in getattr(cir, "functions", []) or []:
        if getattr(f, "name", None) == fn_name:
            return f

    return None


def _is_function_modeled(cir, fn_name: str) -> Tuple[bool, str]:
    """
    Fail-closed soundness rule:
      - If parser did not model function body, do not treat Z3 results as sound.

    Robustness:
      - If model_source is 'solcx' and body_len > 0, treat as modeled even if
        the parser forgot to set modeled=True.
    """
    fn = _find_function_ir(cir, fn_name)

    if fn is None:
        return False, f"Function '{fn_name}' not found in parsed IR."

    src = getattr(fn, "model_source", "unknown")
    body = getattr(fn, "body", []) or []
    body_len = len(body)
    modeled_flag = bool(getattr(fn, "modeled", False))

    MODELED_SOURCES = {"slither", "solcx", "solcx+regex-body", "regex-body"}
    if src in MODELED_SOURCES and body_len > 0:
        return True, f"Modeled OK (source={src}, body_len={body_len})."

    if (not modeled_flag) or body_len == 0:
        return False, (
            f"Function body not modeled "
            f"(source={src}, modeled={modeled_flag}, body_len={body_len})."
        )

    return True, f"Modeled OK (source={src}, body_len={body_len})."


def _compile_specs_safely(
    mgr: InvariantManager,
    specs: List[InvariantSpec],
    model,
) -> Tuple[List[InvariantSpec], List[CompiledInvariant], List[_RejectedResult]]:
    """
    Compile invariants one-by-one so unsupported symbols/ops do not crash the whole run.

    Returns:
      - kept_specs: successfully compiled specs
      - compiled: CompiledInvariant objects corresponding to kept_specs
      - rejected_results: _RejectedResult objects for compile failures
    """
    kept_specs: List[InvariantSpec] = []
    compiled: List[CompiledInvariant] = []
    rejected: List[_RejectedResult] = []

    for i, sp in enumerate(specs):
        name = (
            getattr(sp, "source_line", None)
            or getattr(sp, "raw_line", None)
            or getattr(sp, "line", None)
            or sp.message
            or sp.template
            or f"invariant_{i + 1}"
        )

        try:
            z = mgr._compile_one(sp, model)
            kept_specs.append(sp)
            compiled.append(CompiledInvariant(name=name, z3_bool=z, raw=sp))
        except Exception as e:
            rejected.append(
                _RejectedResult(
                    name=name,
                    reason=f"{type(e).__name__}: {e}",
                )
            )

    return kept_specs, compiled, rejected

# ----------------------------
# Built-in demo invariants
# ----------------------------
def build_invariants_for_token(func_name: str, model):
    """
    Invariants for ERC20-ish tokens and a branchy demo.

    These are useful for debugging and demos, but when --llm-invariants is used
    together with --no-builtin-fallback, they are NOT used as a fallback.
    """
    specs = []

    has_balances = "balances" in model.pre and "balances" in model.post
    has_totalsupply = "totalSupply" in model.pre and "totalSupply" in model.post

    if func_name == "transfer":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="Conserve totalSupply on transfer",
                    expr={"op": "==", "args": ["post.totalSupply", "pre.totalSupply"]},
                )
            )

        if has_balances:
            specs.append(
                InvariantSpec(
                    message="Sender+Recipient sum conserved",
                    expr={
                        "op": "==",
                        "args": [
                            {
                                "op": "+",
                                "args": [
                                    {"op": "select", "args": ["post.balances", "meta.sender"]},
                                    {"op": "select", "args": ["post.balances", "arg.to"]},
                                ],
                            },
                            {
                                "op": "+",
                                "args": [
                                    {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                    {"op": "select", "args": ["pre.balances", "arg.to"]},
                                ],
                            },
                        ],
                    },
                )
            )

            specs.append(
                InvariantSpec(
                    message="Sender balance decreases by amount (to != sender)",
                    expr={
                        "op": "implies",
                        "args": [
                            {"op": "!=", "args": ["arg.to", "meta.sender"]},
                            {
                                "op": "==",
                                "args": [
                                    {"op": "select", "args": ["post.balances", "meta.sender"]},
                                    {
                                        "op": "-",
                                        "args": [
                                            {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                            "arg.amount",
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                )
            )

            specs.append(
                InvariantSpec(
                    message="Recipient balance increases by amount (to != sender)",
                    expr={
                        "op": "implies",
                        "args": [
                            {"op": "!=", "args": ["arg.to", "meta.sender"]},
                            {
                                "op": "==",
                                "args": [
                                    {"op": "select", "args": ["post.balances", "arg.to"]},
                                    {
                                        "op": "+",
                                        "args": [
                                            {"op": "select", "args": ["pre.balances", "arg.to"]},
                                            "arg.amount",
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                )
            )

    elif func_name == "mint":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="Mint increases totalSupply by amount",
                    expr={
                        "op": "==",
                        "args": [
                            "post.totalSupply",
                            {"op": "+", "args": ["pre.totalSupply", "arg.amount"]},
                        ],
                    },
                )
            )

        if has_balances:
            specs.append(
                InvariantSpec(
                    message="Minter balance increases by amount",
                    expr={
                        "op": "==",
                        "args": [
                            {"op": "select", "args": ["post.balances", "meta.sender"]},
                            {
                                "op": "+",
                                "args": [
                                    {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                    "arg.amount",
                                ],
                            },
                        ],
                    },
                )
            )

    elif func_name == "burn":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="Burn decreases totalSupply by amount",
                    expr={
                        "op": "==",
                        "args": [
                            "post.totalSupply",
                            {"op": "-", "args": ["pre.totalSupply", "arg.amount"]},
                        ],
                    },
                )
            )

        if has_balances:
            specs.append(
                InvariantSpec(
                    message="Burner balance decreases by amount",
                    expr={
                        "op": "==",
                        "args": [
                            {"op": "select", "args": ["post.balances", "meta.sender"]},
                            {
                                "op": "-",
                                "args": [
                                    {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                    "arg.amount",
                                ],
                            },
                        ],
                    },
                )
            )

    elif func_name == "tweak":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="tweak changes totalSupply by exactly x (branch-aware)",
                    expr={
                        "op": "ite",
                        "args": [
                            {"op": ">", "args": ["arg.x", 10]},
                            {
                                "op": "==",
                                "args": [
                                    "post.totalSupply",
                                    {"op": "+", "args": ["pre.totalSupply", "arg.x"]},
                                ],
                            },
                            {
                                "op": "==",
                                "args": [
                                    "post.totalSupply",
                                    {"op": "-", "args": ["pre.totalSupply", "arg.x"]},
                                ],
                            },
                        ],
                    },
                )
            )

    if not specs:
        specs.append(
            InvariantSpec(
                message="Trivial true",
                expr={"op": "==", "args": [1, 1]},
            )
        )

    return specs


# ----------------------------
# Refinement helpers
# ----------------------------
def _count_violations(results) -> int:
    return sum(1 for r in results if getattr(r, "status", "") == "VIOLATED")


def _summarize_refinement(stats: dict) -> None:
    if not stats:
        return

    print("\n[refine] Summary:")

    for k in sorted(stats.keys()):
        print(f"  - {k}: {stats[k]}")


def _spec_to_json(sp: InvariantSpec):
    return {
        "template": sp.template,
        "params": sp.params or {},
        "expr": sp.expr,
        "message": sp.message,
        "on_success_only": getattr(sp, "on_success_only", True),
    }


# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser(
        description=(
            "InvGuard Z3Checker driver with fail-closed LLM invariant handling, "
            "JSONL output, and optional counterexample-guided refinement."
        )
    )

    ap.add_argument("sol_file", help="Path to the Solidity file, e.g., examples/SimpleToken.sol")
    ap.add_argument("-c", "--contract", default=None, help="Contract name, optional")
    ap.add_argument("-f", "--function", default=None, help="Function name")
    ap.add_argument(
        "--llm-invariants",
        default=None,
        help="Path to plaintext/markdown invariants from InvGetter, one per line.",
    )

    # New fail-closed / artifact-evaluation flags
    ap.add_argument(
        "--no-builtin-fallback",
        action="store_true",
        help=(
            "Fail closed when --llm-invariants is provided but no LLM invariant "
            "can be translated. Do not silently fall back to built-in invariants."
        ),
    )

    ap.add_argument(
        "--json-results",
        action="store_true",
        help="Emit schema-stable JSONL results for adapter parsing.",
    )

    # Refinement controls
    ap.add_argument(
        "--refine",
        action="store_true",
        help="Enable counterexample-guided invariant rewriting.",
    )

    ap.add_argument(
        "--max-refine-iters",
        type=int,
        default=3,
        help="Max refinement iterations. Default: 3.",
    )

    ap.add_argument(
        "--refine-out",
        default=None,
        help="Optional path to write refined invariants as JSON.",
    )

    args = ap.parse_args()

    # 1) Parse Solidity → ContractIR
    cir = SolidityParser().parse(args.sol_file, contract_name=args.contract)

    # 2) Choose function name
    chosen_fn = args.function

    # [patched] contract-aware selection: real-world files bundle an interface
    # or library before the main contract; if the target function is not in the
    # parsed contract, re-parse each named contract until one defines it.
    if chosen_fn and not any(getattr(fn, "name", None) == chosen_fn
                             for fn in (getattr(cir, "functions", None) or [])):
        import re as _re
        try:
            _src = open(args.sol_file, encoding="utf-8", errors="ignore").read()
        except Exception:
            _src = ""
        _names = _re.findall(r"\bcontract\s+([A-Za-z_]\w*)", _src)
        for _cname in _names:
            try:
                _alt = SolidityParser().parse(args.sol_file, contract_name=_cname)
            except Exception:
                continue
            if any(getattr(fn, "name", None) == chosen_fn
                   for fn in (getattr(_alt, "functions", None) or [])):
                cir = _alt
                break

    if not chosen_fn:
        if getattr(cir, "functions", None):
            chosen_fn = cir.functions[0].name
        else:
            raise RuntimeError("No functions found in contract IR.")

    # 3) Soundness check before model building
    modeled_ok, modeled_msg = _is_function_modeled(cir, chosen_fn)

    if not modeled_ok:
        print("\n=== UNSOUND MODEL WARNING ===")
        print("UNSOUND_MODEL: verifier cannot soundly validate invariants for this function.")
        print("Reason:", modeled_msg)
        print("Action: returning UNVERIFIED_UNSOUND for all invariants.")
        print("=============================\n")

    # 4) Build symbolic model
    # Build even if modeled_ok=False so translator can still resolve symbols when possible.
    builder = SymModelBuilder()
    model = builder.build_for_function_name(cir, chosen_fn)

    # 5) Choose invariants
    mgr = InvariantManager()
    specs: List[InvariantSpec] = []
    used_source = None
    raw_llm_lines: List[str] = []
    pre_results: List[Any] = []

    if args.llm_invariants:
        try:
            from invariants.translator import translate_lines_to_specs
        except Exception as e:
            raise RuntimeError(
                "Could not import invariants.translator. "
                "Make sure invariants/translator.py is present."
            ) from e

        raw_llm_lines = _load_llm_invariants_lines(args.llm_invariants)
        if not raw_llm_lines:
            print("\n[translator] LLM invariant file is empty after loading/cleanup.")

            if args.json_results:
                _emit_json_result(
                    idx=1,
                    inv="<empty-invariant-file>",
                    status="REJECTED_UNSUPPORTED",
                    reason="EMPTY_LLM_INVARIANT_FILE",
                )
            else:
                pretty_print_results([
                    _RejectedResult(
                        name="<empty-invariant-file>",
                        reason="EMPTY_LLM_INVARIANT_FILE",
                    )
                ])

            return
        raw_text = "\n".join(raw_llm_lines) + ("\n" if raw_llm_lines else "")

        tr = translate_lines_to_specs(raw_text, model)

        if tr.rejected:
            print("\n[translator] Rejected lines (reason shown):")

            for line, reason in tr.rejected[:50]:
                print(f"  - {line}  =>  {reason}")

            if len(tr.rejected) > 50:
                print("  ...")

        if not tr.accepted:
            print("\n[translator] No valid invariants accepted from LLM.")

            # Emit translator rejected lines first if JSON mode is on.
            # Then decide whether to fall back or fail closed.
            if args.no_builtin_fallback:
                print("[translator] Built-in fallback disabled by --no-builtin-fallback.")
                print("[translator] Returning REJECTED_UNSUPPORTED for all LLM invariants.")

                reason = "TRANSLATION_FAILED_NO_BUILTIN_FALLBACK"

                if args.json_results:
                    if raw_llm_lines:
                        _emit_json_rejected_lines(raw_llm_lines, reason=reason)
                    else:
                        _emit_json_result(
                            idx=1,
                            inv="<no-llm-invariants>",
                            status="REJECTED_UNSUPPORTED",
                            reason=reason,
                        )

                else:
                    results = [
                        _RejectedResult(name=line, reason=reason)
                        for line in raw_llm_lines
                    ]

                    if not results:
                        results = [_RejectedResult(name="<no-llm-invariants>", reason=reason)]

                    pretty_print_results(results)

                return

            print("[translator] Falling back to built-ins.")
            specs = build_invariants_for_token(model.function_name, model)
            used_source = "built-ins"

        else:
            print(f"\n[translator] Accepted {len(tr.accepted)} invariants from LLM.")
            specs = _attach_original_lines_to_specs(tr.accepted, raw_llm_lines)
            used_source = "LLM-translated"

            # Keep rejected translator lines as explicit rejected results.
            # They are not solver-checked, but JSONL should preserve them.
            for line, reason in getattr(tr, "rejected", []) or []:
                pre_results.append(
                    _RejectedResult(
                        name=str(line),
                        reason=f"TRANSLATOR_REJECTED: {reason}",
                    )
                )

    else:
        specs = build_invariants_for_token(model.function_name, model)
        used_source = "built-ins"

    # 6) Report parsing/modeling notes
    print(f"\nFunction: {model.function_name}  (invariants: {used_source})")

    if getattr(model, "notes", None):
        print("Notes:")

        for n in model.notes:
            print("  -", n)

    # 7) If the function/model is unsound, fail closed.
    if not modeled_ok:
        unsound_results: List[Any] = []

        if specs:
            for s in specs:
                unsound_results.append(
                    _UnsoundResult(
                        name=(
                            getattr(s, "source_line", None)
                            or getattr(s, "raw_line", None)
                            or getattr(s, "line", None)
                            or getattr(s, "message", "")
                            or getattr(s, "template", "")
                            or "<invariant>"
                        ),
                        reason=f"UNSOUND_MODEL: {modeled_msg}",
                    )
                )
        elif raw_llm_lines:
            for line in raw_llm_lines:
                unsound_results.append(
                    _UnsoundResult(
                        name=line,
                        reason=f"UNSOUND_MODEL: {modeled_msg}",
                    )
                )

        if not unsound_results:
            unsound_results = [
                _UnsoundResult(
                    name="<no-invariants>",
                    reason=f"UNSOUND_MODEL: {modeled_msg}",
                )
            ]

        all_results = list(unsound_results) + list(pre_results)

        if args.json_results:
            _emit_json_results_from_objects(all_results)
        else:
            pretty_print_results(all_results)

        return

    # 8) Compile invariants safely.
    specs, compiled, rejected_results = _compile_specs_safely(mgr, specs, model)

    # 9) Check with centralized checker.
    print("\n=== Invariant Checks ===")
    results = check_compiled_invariants(model, compiled)

    all_results = list(results) + list(rejected_results) + list(pre_results)

    if args.json_results:
        _emit_json_results_from_objects(all_results)
    else:
        pretty_print_results(all_results)

    # 10) Optional refinement loop.
    if args.refine:
        if rewrite_specs is None:
            raise RuntimeError(
                "Refinement requested with --refine, but invariants/invariant_rewriter.py "
                "is missing or does not expose rewrite_specs(...)."
            )

        it = 0

        total_stats = {
            "iters": 0,
            "violations_initial": _count_violations(results),
            "violations_final": None,
            "rewritten": 0,
            "dropped": 0,
            "unchanged": 0,
        }

        while it < args.max_refine_iters and _count_violations(results) > 0:
            it += 1

            print(
                f"\n[refine] Iteration {it}/{args.max_refine_iters} "
                f"(violations={_count_violations(results)})"
            )

            specs, stats = rewrite_specs(specs, results, model)

            total_stats["iters"] = it

            for k in ("rewritten", "dropped", "unchanged"):
                if k in stats and isinstance(stats[k], int):
                    total_stats[k] += stats[k]

            _summarize_refinement(stats)

            specs, compiled, rejected_results = _compile_specs_safely(mgr, specs, model)

            print("\n=== Invariant Checks after refinement ===")
            results = check_compiled_invariants(model, compiled)

            all_results = list(results) + list(rejected_results) + list(pre_results)

            if args.json_results:
                _emit_json_results_from_objects(all_results)
            else:
                pretty_print_results(all_results)

        total_stats["violations_final"] = _count_violations(results)

        print("\n[refine] Finished.")
        print(
            f"[refine] Violations: "
            f"{total_stats['violations_initial']} -> {total_stats['violations_final']}"
        )
        print(
            f"[refine] Rewritten: {total_stats['rewritten']}  "
            f"Dropped: {total_stats['dropped']}  "
            f"Unchanged: {total_stats['unchanged']}"
        )

        if args.refine_out:
            with open(args.refine_out, "w", encoding="utf-8") as f:
                json.dump([_spec_to_json(s) for s in specs], f, indent=2)

            print(f"[refine] Wrote refined invariants JSON to: {args.refine_out}")


if __name__ == "__main__":
    main()