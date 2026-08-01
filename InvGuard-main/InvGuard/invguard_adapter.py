# flow_1_files/invguard_adapter.py
import os
import sys
import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class InvGuardResult:
    def __init__(self):
        # Only invariants that are actually proved HOLDS by the checker.
        self.verified: List[str] = []

        # Violated invariants with counterexample models.
        # Schema:
        #   {"name": str, "line": str, "model": Dict[str, str]}
        self.failed: List[Dict[str, Any]] = []

        # Unknown/unverified invariants.
        # IMPORTANT: These are excluded from verified output and Flow-2.
        self.unknown: List[str] = []

        # Backward-compatibility only.
        # Do not treat this as trusted. It aliases unknown.
        self.trusted = self.unknown

        # Unsound/unverified invariants.
        # Schema:
        #   {"name": str, "line": str, "reason": str}
        self.unsound: List[Dict[str, Any]] = []

        # Rejected/unsupported invariants.
        # Schema:
        #   {"name": str, "line": str, "reason": str}
        self.rejected: List[Dict[str, Any]] = []

        # Full textual report from the checker/adapter.
        self.report_lines: List[str] = []

        # Fail-closed status flags.
        self.llm_invariants_accepted: bool = True
        self.used_builtin_fallback: bool = False


_PLACEHOLDER_RE = re.compile(r"^<inv_\d+>$")


def _sanitize_invariant(line: str) -> str:
    """
    Clean up common formatting mistakes in generated invariants.
    """
    line = (line or "").strip()

    while ")))" in line:
        line = line.replace(")))", "))")

    if line.endswith("))") and not line.endswith("(())"):
        line = line[:-1]

    line = line.replace("=>", "->").strip()
    return line


def _is_placeholder_inv(s: str) -> bool:
    return bool(_PLACEHOLDER_RE.fullmatch((s or "").strip()))


def _is_trivial_invariant(s: str) -> bool:
    t = (s or "").strip().lower()
    return t in {
        "true",
        "trivial true",
        "meta.sender == meta.sender",
        "(true)",
    }


def _is_bad_verified_candidate(s: str) -> bool:
    """
    Anything matching this must never enter verified output.
    """
    t = (s or "").strip()

    if not t:
        return True

    if _is_placeholder_inv(t):
        return True

    if _is_trivial_invariant(t):
        return True

    bad_markers = [
        "UNVERIFIED_UNSOUND",
        "REJECTED_UNSUPPORTED",
        "TRANSLATION_FAILED",
        "BUILTIN_FALLBACK",
        "LLM_INVARIANT_NOT_TRANSLATED",
        "PLACEHOLDER_INVARIANT",
        "reason=",
    ]

    return any(m in t for m in bad_markers)


def _used_builtin_fallback(out_lines: List[str]) -> bool:
    """
    Detect whether cli.driver fell back to built-in invariants.

    Important:
    - Built-in fallback is useful for debugging.
    - Built-in fallback must NOT be counted as verified LLM invariants.
    """
    joined = "\n".join(out_lines)

    return (
        "Falling back to built-ins" in joined
        or "(invariants: built-ins)" in joined
        or "invariants: built-ins" in joined
    )


def _parse_counterexample_bindings(lines: List[str], start_idx: int) -> Tuple[Dict[str, str], int]:
    """
    LEGACY parser.

    Given stdout lines and an index pointing at the 'Counterexample:' line,
    parse subsequent indented bindings:
        '    k = v'

    Returns:
        (model_dict, next_index)
    """
    model: Dict[str, str] = {}
    i = start_idx + 1

    while i < len(lines):
        ln = lines[i]

        if ln.startswith("- "):
            break

        if ln.strip().startswith("==="):
            break

        if ln.startswith("    "):
            s = ln.strip()

            if s == "...":
                i += 1
                continue

            if "=" in s:
                k, v = s.split("=", 1)
                model[k.strip()] = v.strip()

            i += 1
            continue

        if ln.strip():
            break

        i += 1

    return model, i


def _try_parse_json_results(out_lines: List[str]) -> Optional[List[Dict[str, Any]]]:
    """
    Preferred parser: JSONL results emitted by cli.driver.

    Expected JSON object per invariant:
      {
        "idx": 1,
        "inv": "<invariant string>",
        "status": "HOLDS" | "VIOLATED" | "UNKNOWN"
                  | "UNVERIFIED_UNSOUND"
                  | "REJECTED_UNSUPPORTED",
        "reason": "...",
        "model": {"k": "v"}
      }

    Returns:
        list[dict] or None if no JSONL results are detected.
    """
    parsed: List[Dict[str, Any]] = []
    saw_any = False

    for ln in out_lines:
        s = (ln or "").strip()

        if not s:
            continue

        if not s.startswith("{"):
            continue

        try:
            obj = json.loads(s)
        except Exception:
            continue

        if not isinstance(obj, dict):
            continue

        if "status" not in obj:
            continue

        if "inv" not in obj and "line" not in obj:
            continue

        saw_any = True
        parsed.append(obj)

    return parsed if saw_any else None


def _load_raw_invariants(invariants_txt_path: str) -> List[str]:
    path = Path(invariants_txt_path)

    if not path.exists():
        return []

    return [
        _sanitize_invariant(l.strip())
        for l in path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


def _reject_all_raw_invariants(
    result: InvGuardResult,
    raw_lines: List[str],
    reason: str,
) -> None:
    for i, inv in enumerate(raw_lines, start=1):
        result.rejected.append({
            "name": f"inv_{i}",
            "line": inv,
            "reason": reason,
        })


def _safe_append_verified(result: InvGuardResult, inv_line: str, idx_int: int) -> None:
    inv_line = _sanitize_invariant(inv_line)

    if _is_bad_verified_candidate(inv_line):
        result.rejected.append({
            "name": f"inv_{idx_int}",
            "line": inv_line,
            "reason": "NOT_A_REAL_VERIFIED_INVARIANT",
        })
        return

    if inv_line not in result.verified:
        result.verified.append(inv_line)


def _write_result_files(
    result: InvGuardResult,
    contract_path: str,
    function_name: Optional[str],
) -> None:
    """
    Write adapter outputs.

    Important policy:
    - verified_invariants.*.txt contains ONLY genuinely verified invariants.
    - unknown/trusted invariants are written separately and excluded from Flow-2.
    - rejected and unsound invariants are written separately.
    """
    base_dir = Path(contract_path).parent

    if function_name:
        prefix = f"verified_invariants.{function_name}"
    else:
        prefix = "verified_invariants.global"

    verified_file = base_dir / f"{prefix}.txt"
    unknown_file = base_dir / f"{prefix}.unknown.txt"
    unsound_file = base_dir / f"{prefix}.unsound.txt"
    rejected_file = base_dir / f"{prefix}.rejected.txt"
    summary_file = base_dir / f"{prefix}.summary.json"

    with open(verified_file, "w", encoding="utf-8") as f:
        f.write("# VERIFIED INVARIANTS ONLY\n")
        f.write("# UNKNOWN/TRUSTED/UNSOUND/REJECTED invariants are excluded.\n")

        for inv in result.verified:
            if not _is_bad_verified_candidate(inv):
                f.write(inv + "\n")

    with open(unknown_file, "w", encoding="utf-8") as f:
        if result.unknown:
            f.write("# UNKNOWN / NOT VERIFIED / EXCLUDED FROM FLOW-2\n")
            for inv in result.unknown:
                f.write(inv + "\n")

    with open(unsound_file, "w", encoding="utf-8") as f:
        if result.unsound:
            f.write("# UNSOUND / UNVERIFIED / EXCLUDED FROM FLOW-2\n")
            for u in result.unsound:
                line = u.get("line", "")
                reason = u.get("reason", "")
                if reason:
                    f.write(f"{line}  # reason={reason}\n")
                else:
                    f.write(f"{line}\n")

    with open(rejected_file, "w", encoding="utf-8") as f:
        if result.rejected:
            f.write("# REJECTED / UNSUPPORTED / EXCLUDED FROM FLOW-2\n")
            for r in result.rejected:
                line = r.get("line", "")
                reason = r.get("reason", "")
                if reason:
                    f.write(f"{line}  # reason={reason}\n")
                else:
                    f.write(f"{line}\n")

    summary = {
        "verified_count": len(result.verified),
        "violated_count": len(result.failed),
        "unknown_count": len(result.unknown),
        "unsound_count": len(result.unsound),
        "rejected_count": len(result.rejected),
        "llm_invariants_accepted": result.llm_invariants_accepted,
        "used_builtin_fallback": result.used_builtin_fallback,
        "verified_file": str(verified_file),
        "unknown_file": str(unknown_file),
        "unsound_file": str(unsound_file),
        "rejected_file": str(rejected_file),
        "policy": (
            "fail_closed: only HOLDS invariants from LLM translation/checking "
            "are written to verified_invariants.*.txt"
        ),
    }

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[ADAPTER] Verified invariants written to {verified_file}")

    if result.unknown:
        print(f"[ADAPTER] UNKNOWN invariants written to {unknown_file}")

    if result.unsound:
        print(f"[ADAPTER] UNSOUND invariants written to {unsound_file}")

    if result.rejected:
        print(f"[ADAPTER] REJECTED invariants written to {rejected_file}")

    print(f"[ADAPTER] Summary written to {summary_file}")


def _print_final_summary(result: InvGuardResult) -> None:
    print("\n=== [ADAPTER] FINAL INVARIANT SUMMARY ===")

    if result.used_builtin_fallback:
        print("⚠️ Built-in fallback detected.")
        print("   Built-in results are NOT counted as verified LLM invariants.")

    print("✅ Verified invariants:")
    for inv in result.verified:
        print("   -", inv)

    print("❌ Violated invariants:")
    for f in result.failed:
        ce_preview = ""

        if isinstance(f.get("model"), dict) and f["model"]:
            items = list(f["model"].items())[:5]
            ce_preview = " | " + ", ".join([f"{k}={v}" for k, v in items])

        print("   -", f.get("line", "<missing>"), ce_preview)

    print("❔ Unknown / not verified invariants (excluded):")
    for inv in result.unknown:
        print("   -", inv)

    print("🚫 Rejected / unsupported invariants (excluded):")
    for r in result.rejected:
        rsn = r.get("reason", "")
        print("   -", r.get("line", "<missing>"), (f" | reason={rsn}" if rsn else ""))

    print("⚠️ UNSOUND / unverified invariants (excluded):")
    for u in result.unsound:
        rsn = u.get("reason", "")
        print("   -", u.get("line", "<missing>"), (f" | reason={rsn}" if rsn else ""))

    print("========================================\n")


def run_invguard_core(
    z3checker_root: str,
    contract_path: str,
    invariants_txt_path: str,
    function_name: Optional[str] = None,
) -> InvGuardResult:
    """
    Adapter for InvGuard/Z3Checker.

    ICSE-safe behavior:
      - LLM outputs are proposals only.
      - Only checker-confirmed HOLDS invariants are verified.
      - UNKNOWN is excluded, not trusted.
      - UNSOUND is excluded.
      - REJECTED is excluded.
      - Built-in fallback is ignored for verified LLM invariant accounting.
      - Placeholder invariants such as <inv_1> are rejected.
      - The adapter writes schema-stable side files for later Flow-2 use.
    """
    cmd = [sys.executable, "-m", "cli.driver", contract_path]

    if function_name:
        cmd += ["-f", function_name]

    cmd += [
        "--llm-invariants",
        invariants_txt_path,
        "--no-builtin-fallback",
        "--json-results",
    ]

    print(f"[ADAPTER] launching: {' '.join(cmd)} (cwd={z3checker_root})")

    try:
        proc = subprocess.run(
            cmd,
            cwd=z3checker_root,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("INVGUARD_Z3_TIMEOUT_SEC", "120")),
        )
    except subprocess.TimeoutExpired as e:
        result = InvGuardResult()
        result.report_lines.append(f"[adapter] cmd: {' '.join(cmd)}")
        result.report_lines.append(f"[adapter] cwd: {z3checker_root}")
        result.report_lines.append("[adapter] TIMEOUT")
        result.report_lines.append(str(e))

        result.unsound.append({
            "name": "timeout",
            "line": "<solver-timeout>",
            "reason": "Z3CHECKER_TIMEOUT",
        })

        _print_final_summary(result)
        _write_result_files(result, contract_path, function_name)
        return result

    print(f"[ADAPTER] returncode={proc.returncode}")

    if proc.stderr:
        lines = proc.stderr.strip().splitlines()
        head = "\n".join(lines[:60])
        print(
            f"[ADAPTER] stderr (head):\n{head}\n"
            f"{'[... truncated ...]' if len(lines) > 60 else ''}"
        )

    result = InvGuardResult()
    out_lines = (proc.stdout or "").splitlines()
    err = proc.stderr or ""
    raw_lines = _load_raw_invariants(invariants_txt_path)

    result.report_lines.append(f"[adapter] cmd: {' '.join(cmd)}")
    result.report_lines.append(f"[adapter] cwd: {z3checker_root}")
    result.report_lines.append(f"[adapter] returncode: {proc.returncode}")
    result.report_lines += out_lines

    if proc.returncode != 0:
        if err.strip():
            result.report_lines.append("[adapter] STDERR:")
            result.report_lines.append(err.strip())

        raise RuntimeError(
            f"Z3Checker failed with return code {proc.returncode}. "
            f"This is an infrastructure/configuration failure. "
            f"See report_lines for details."
        )

    # ------------------------------------------------------------------
    # Fail-closed: if old driver fell back to built-ins, do not parse
    # HOLDS results as LLM invariant verification.
    # ------------------------------------------------------------------
    if _used_builtin_fallback(out_lines):
        result.llm_invariants_accepted = False
        result.used_builtin_fallback = True

        result.report_lines.append(
            "[adapter] LLM invariants were not accepted by translator; "
            "built-in fallback detected and ignored for verified accounting."
        )

        _reject_all_raw_invariants(
            result=result,
            raw_lines=raw_lines,
            reason="LLM_INVARIANT_NOT_TRANSLATED_BUILTIN_FALLBACK_IGNORED",
        )

        _print_final_summary(result)
        _write_result_files(result, contract_path, function_name)
        return result

    # ------------------------------------------------------------------
    # Preferred path: schema-stable JSONL results from cli.driver.
    # ------------------------------------------------------------------
    json_items = _try_parse_json_results(out_lines)

    if json_items is not None:
        for j, obj in enumerate(json_items, start=1):
            idx = obj.get("idx")

            try:
                idx_int = int(idx) if idx is not None else j
            except Exception:
                idx_int = j

            inv_line = obj.get("inv") or obj.get("line") or ""
            inv_line = _sanitize_invariant(str(inv_line))

            if not inv_line and 1 <= idx_int <= len(raw_lines):
                inv_line = raw_lines[idx_int - 1]

            if not inv_line:
                inv_line = f"<inv_{idx_int}>"

            status = str(obj.get("status") or "").upper()
            model = obj.get("model") if isinstance(obj.get("model"), dict) else {}
            reason = str(obj.get("reason") or obj.get("msg") or "")

            if _is_placeholder_inv(inv_line):
                result.rejected.append({
                    "name": f"inv_{idx_int}",
                    "line": inv_line,
                    "reason": "PLACEHOLDER_INVARIANT_NOT_REAL",
                })
                continue

            if _is_trivial_invariant(inv_line):
                result.rejected.append({
                    "name": f"inv_{idx_int}",
                    "line": inv_line,
                    "reason": "TRIVIAL_INVARIANT_NOT_USEFUL",
                })
                continue

            if "UNSOUND" in status or "UNVERIFIED" in status:
                result.unsound.append({
                    "name": f"inv_{idx_int}",
                    "line": inv_line,
                    "reason": reason or "UNVERIFIED_UNSOUND",
                })
                continue

            if "REJECTED" in status or "UNSUPPORTED" in status:
                result.rejected.append({
                    "name": f"inv_{idx_int}",
                    "line": inv_line,
                    "reason": reason or "REJECTED_UNSUPPORTED",
                })
                continue

            if "HOLD" in status:
                _safe_append_verified(result, inv_line, idx_int)
                continue

            if "VIOL" in status or status == "FAILED":
                result.failed.append({
                    "name": f"inv_{idx_int}",
                    "line": inv_line,
                    "model": {str(k): str(v) for k, v in (model or {}).items()},
                })
                continue

            # UNKNOWN / anything else is excluded.
            result.unknown.append(inv_line)

    else:
        # ------------------------------------------------------------------
        # Legacy text scraping.
        #
        # This exists only for temporary compatibility. It is fail-closed:
        # placeholders/trivial/fallbacks are excluded.
        # ------------------------------------------------------------------
        idx = 0
        i = 0

        while i < len(out_lines):
            ln = out_lines[i]
            s = ln.strip()

            if s.startswith("- "):
                idx += 1

                raw = raw_lines[idx - 1] if idx - 1 < len(raw_lines) else f"<inv_{idx}>"
                raw = _sanitize_invariant(raw)

                if _is_placeholder_inv(raw):
                    result.rejected.append({
                        "name": f"inv_{idx}",
                        "line": raw,
                        "reason": "PLACEHOLDER_INVARIANT_NOT_REAL",
                    })
                    i += 1
                    continue

                if _is_trivial_invariant(raw):
                    result.rejected.append({
                        "name": f"inv_{idx}",
                        "line": raw,
                        "reason": "TRIVIAL_INVARIANT_NOT_USEFUL",
                    })
                    i += 1
                    continue

                if "UNVERIFIED_UNSOUND" in s or "UNSOUND" in s:
                    result.unsound.append({
                        "name": f"inv_{idx}",
                        "line": raw,
                        "reason": "UNVERIFIED_UNSOUND",
                    })

                elif "REJECTED" in s or "UNSUPPORTED" in s:
                    result.rejected.append({
                        "name": f"inv_{idx}",
                        "line": raw,
                        "reason": "REJECTED_UNSUPPORTED",
                    })

                elif "HOLDS" in s:
                    _safe_append_verified(result, raw, idx)

                elif "VIOLATED" in s:
                    result.failed.append({
                        "name": f"inv_{idx}",
                        "line": raw,
                        "model": {},
                    })

                else:
                    result.unknown.append(raw)

                i += 1
                continue

            if s.startswith("Counterexample:") or ln.lstrip().startswith("Counterexample:"):
                if result.failed:
                    model_dict, next_i = _parse_counterexample_bindings(out_lines, i)

                    if isinstance(result.failed[-1].get("model"), dict):
                        result.failed[-1]["model"].update(model_dict)
                    else:
                        result.failed[-1]["model"] = model_dict

                    i = next_i
                    continue

            i += 1

    # Final safety scrub: verified must contain only real invariants.
    scrubbed_verified: List[str] = []

    for inv in result.verified:
        if _is_bad_verified_candidate(inv):
            result.rejected.append({
                "name": "scrubbed_verified",
                "line": inv,
                "reason": "REMOVED_FROM_VERIFIED_BY_FINAL_SAFETY_SCRUB",
            })
            continue

        if inv not in scrubbed_verified:
            scrubbed_verified.append(inv)

    result.verified = scrubbed_verified

    _print_final_summary(result)
    _write_result_files(result, contract_path, function_name)

    return result