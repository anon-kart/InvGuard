# flow_1_files/tools.py
from agents import function_tool
from typing import List
import os
import re
from pathlib import Path

# ==============================
# Base execution directory (ONE source of truth)
#   All Flow-1 artifacts will be written here:
#   - contract.sol
#   - invariants.txt
#   - z3_validation_report*.txt
#   - verified_invariants.<function>.txt  (per-function)
#   - verified_invariants.txt             (merged for Flow-2)
# ==============================

THIS_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
BASE_EXECUTION_DIR = os.path.join(REPO_ROOT, "run_outputs", "flow1")

# ------------------------------
# Normalizer helpers
# ------------------------------
_unicode_ops = {
    "⇒": "->",
    "→": "->",
    "≥": ">=",
    "≤": "<=",
    "≠": "!=",
    "—": "-",
    "–": "-",
}

def _replace_unicode_ops(s: str) -> str:
    for bad, good in _unicode_ops.items():
        s = s.replace(bad, good)
    return s

def normalize_invariant_line(s: str) -> str:
    """
    Rewrite an invariant string into the restricted DSL expected by Z3Checker.
    """
    t = (s or "").strip()

    # Trim bullets / code fences / trailing punctuation
    t = t.strip("`•*- \t")
    t = _replace_unicode_ops(t)

    # ✅ REQUIRED CHANGE: canonicalize implication token to "->"
    # (do NOT force "->" into "=>", it breaks matching/dedup downstream)
    t = t.replace("=>", "->")

    # msg.* → meta.*
    t = re.sub(r"\bmsg\.sender\b", "meta.sender", t)
    t = re.sub(r"\bmsg\.value\b", "meta.value", t)

    # ✅ REQUIRED CHANGE: collapse common invalid pre/post value spellings into meta.value
    # (pre.value / post.value / pre.meta.value / post.meta.value are not supported symbols in Z3Checker)
    t = re.sub(r"\bpre\.meta\.value\b", "meta.value", t)
    t = re.sub(r"\bpost\.meta\.value\b", "meta.value", t)
    t = re.sub(r"\bpre\.value\b", "meta.value", t)
    t = re.sub(r"\bpost\.value\b", "meta.value", t)

    # ✅ Helpful hardening: collapse accidental namespaces on meta.*
    t = re.sub(r"\b(pre|post)\.meta\.", "meta.", t)

    # ✅ only rewrite bare `amount`, not already `arg.amount`
    t = re.sub(r"(?<!arg\.)\bamount\b", "arg.amount", t)

    # ✅ hardening: collapse accidental duplicates if they still occur
    t = t.replace("arg.arg.amount", "arg.amount")

    # Common typos
    t = t.replace("balancer", "balances")

    # Underscore variants
    t = t.replace("pre_balances", "pre.balances")
    t = t.replace("post_balances", "post.balances")
    t = t.replace("pre_balance", "pre.balances")
    t = t.replace("post_balance", "post.balances")
    t = t.replace("pre.balances.", "pre.balances")
    t = t.replace("post.balances.", "post.balances")

    # Paren indexing → select(...)
    t = re.sub(
        r"(pre|post)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([^)]+?)\s*\)",
        r"select(\1.\2, \3)", t
    )

    # Bracket indexing → select(...)
    t = re.sub(
        r"pre\.([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([^\]]+?)\s*\]",
        r"select(pre.\1, \2)", t
    )
    t = re.sub(
        r"post\.([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([^\]]+?)\s*\]",
        r"select(post.\1, \2)", t
    )

    # Fallbacks without pre/post
    t = re.sub(r"\bbalances\s*\[\s*([^\]]+?)\s*\]", r"select(post.balances, \1)", t)
    t = re.sub(r"\bbalances\s*\(\s*([^)]+?)\s*\)", r"select(post.balances, \1)", t)

    # Specific common case
    t = re.sub(
        r"\bbalances\s*\(\s*meta\.sender\s*\)",
        "select(post.balances, meta.sender)",
        t
    )

    # Cleanup spacing
    t = re.sub(r"select\(\s*", "select(", t)
    t = re.sub(r"\s*,\s*", ", ", t)
    t = re.sub(r"\s*\)", ")", t)
    t = re.sub(r"\s{2,}", " ", t).strip()

    return t

def _preprocess_solidity_for_solcx(src: str) -> str:
    """
    Solidity source normalization used before writing run_outputs/flow1/contract.sol.

    IMPORTANT: This function is the ONLY place we touch `.call{value: ...}()`.
    Do NOT duplicate this logic elsewhere, or you can create invalid Solidity like:
        .call{value: x}("",
    """
    if not src:
        return src

    # --------------------------------------------------
    # Fix legacy ONLY: .call{value: x}()  -> .call{value: x}("")
    #  - Do NOT touch .call{value: x}("") (already correct)
    #  - Do NOT touch .call{value: x}(...) (non-empty args)
    # --------------------------------------------------
    call_value = r"(\.call\s*\{\s*value\s*:\s*[^}]+\s*\})"
    src = re.sub(
        rf"{call_value}\s*\(\s*\)",
        r'\1("")',
        src,
        flags=re.M,
    )

    # --------------------------------------------------
    # ✅ REQUIRED FIX: undo invalid 2-arg low-level call emissions
    #   .call{...}("" , 0)  -> .call{...}("")
    # This is contract-agnostic and safe because Solidity .call takes ONE bytes arg.
    # We only rewrite when the first arg is exactly an empty string literal.
    # --------------------------------------------------
    src = re.sub(
        r'(\.call\s*\{[^}]*\})\s*\(\s*(\"\"|\'\')\s*,\s*[^)]*\)',
        r'\1(\2)',
        src,
        flags=re.M,
    )

    # --------------------------------------------------
    # HARDENING: undo accidental `{""}` patterns (if any)
    # These cause: ParserError: Expected identifier but got 'StringLiteral'
    # --------------------------------------------------
    src = src.replace('({""})', '("")')
    src = src.replace('{""}', '""')

    return src

# ------------------------------
# Tools
# ------------------------------
@function_tool
def save_contract(contract_code: str, filename: str = "contract.sol") -> str:
    """
    Save contract source into Flow-1 output directory.

    NOTE: We intentionally do NOT perform any extra `.call{value: ...}()` rewriting here.
    That logic lives ONLY in `_preprocess_solidity_for_solcx()` to avoid double-fixing
    and producing invalid Solidity.
    """
    try:
        os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
        if not filename.endswith(".sol"):
            filename += ".sol"
        file_path = os.path.join(BASE_EXECUTION_DIR, filename)

        fixed = _preprocess_solidity_for_solcx(contract_code)

        # Safety checks: refuse to write if we introduced obvious breakage
        if fixed.count('"') % 2 != 0:
            raise RuntimeError("Unbalanced quotes introduced while saving contract (refusing to write).")
        if fixed.count("(") != fixed.count(")"):
            raise RuntimeError("Unbalanced parentheses introduced while saving contract (refusing to write).")

        # Ensure trailing newline for cleaner diffs / toolchains
        if not fixed.endswith("\n"):
            fixed += "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fixed)

        return f"Smart contract successfully saved to: {file_path}"
    except Exception as e:
        return f"Error saving contract: {e}"

@function_tool
def save_invariants(invariants: List[str], filename: str = "invariants.txt") -> str:
    try:
        os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
        if not filename.endswith(".txt"):
            filename += ".txt"
        file_path = os.path.join(BASE_EXECUTION_DIR, filename)

        normed: List[str] = []
        for inv in invariants or []:
            clean = (inv or "").strip()
            if clean:
                normed.append(normalize_invariant_line(clean))

        with open(file_path, "w", encoding="utf-8") as f:
            if normed:
                f.write("\n".join(normed) + "\n")
            else:
                f.write("")

        return f"Invariants successfully saved to: {file_path}"
    except Exception as e:
        return f"Error saving invariants: {e}"

@function_tool
def save_verified_invariants(
    verified: List[str],
    trusted: List[str],
    out_dir: str = None,
    filename: str = "verified_invariants.txt",
) -> str:
    """
    Writes one verified/trusted invariants file (typically per-function).
    If out_dir is None, we default to the SAME Flow-1 output folder so
    Flow-2 can find artifacts consistently under run_outputs/flow1/.
    """
    try:
        if out_dir is None:
            out_dir = BASE_EXECUTION_DIR

        os.makedirs(out_dir, exist_ok=True)
        out_path = Path(out_dir) / filename

        v_norm = [normalize_invariant_line(x) for x in (verified or []) if (x or "").strip()]
        t_norm = [normalize_invariant_line(x) for x in (trusted or []) if (x or "").strip()]

        with open(out_path, "w", encoding="utf-8") as f:
            if v_norm:
                f.write("# VERIFIED INVARIANTS\n")
                for inv in v_norm:
                    f.write(inv + "\n")
            if t_norm:
                if v_norm:
                    f.write("\n")
                f.write("# TRUSTED INVARIANTS\n")
                for inv in t_norm:
                    f.write(inv + "\n")

        print(f"[TOOLS] Wrote verified/trusted invariants to: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"[TOOLS] Error writing verified invariants: {e}")
        return f"Error: {e}"

# ------------------------------
# NEW: Merge per-function verified invariants into one file for Flow-2
# ------------------------------
def merge_verified_invariants(flow1_dir: str = None, out_filename: str = "verified_invariants.txt") -> str:
    """
    Merges all files matching:
      verified_invariants.*.txt
    inside Flow-1 output dir into:
      verified_invariants.txt

    - Strips comments (# ...)
    - Removes blank lines
    - De-duplicates while preserving order
    """
    if flow1_dir is None:
        flow1_dir = BASE_EXECUTION_DIR

    flow1_dir_p = Path(flow1_dir)
    out_path = flow1_dir_p / out_filename

    merged: List[str] = []
    for fpath in sorted(flow1_dir_p.glob("verified_invariants.*.txt")):
        try:
            with open(fpath, "r", encoding="utf-8") as fin:
                for line in fin:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    merged.append(line)
        except Exception as e:
            print(f"[TOOLS] WARNING: Could not read {fpath}: {e}")

    # de-duplicate (preserve order)
    merged = list(dict.fromkeys(merged))

    os.makedirs(flow1_dir_p, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fout:
        if merged:
            fout.write("\n".join(merged) + "\n")
        else:
            fout.write("")

    print(f"[TOOLS] Merged verified invariants → {out_path}")
    return str(out_path)
