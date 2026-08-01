# invariant_normalizer.py
import re
from typing import Optional


def normalize_expression(expr: str) -> Optional[str]:
    """
    Canonical normalization for invariant strings.

    This function MUST be:
      - idempotent
      - whitespace-stable
      - operator-canonical
      - safe for deduplication

    It performs:
      - Solidity alias normalization
      - Implies normalization (=>, -> → ->)
      - Boolean operator canonicalization
      - Struct/map flattening
      - Parenthesis repair
      - Whitespace collapse
      - EARLY rejection of unsupported constructs (e.g., Solidity ternary)
      - ✅ NEW: fix common LLM symbol aliasing (pre.balance -> pre.balances)
    """

    if not expr:
        return None

    s = expr.strip()
    if not s:
        return None

    # -------------------------------------------------
    # 0) Reject unsupported / informal syntax EARLY
    # -------------------------------------------------
    unsupported = [
        "after",
        "before",
        "transfer(",
        "forall",
        "exists",
    ]
    low = s.lower()
    if any(tok in low for tok in unsupported):
        return None

    # Reject Solidity ternary operator (cond ? a : b)
    # This avoids: Unknown symbol '(arg.amount > 0 ? arg.amount : 0)'
    qpos = s.find("?")
    if qpos != -1:
        cpos = s.find(":", qpos + 1)
        if cpos != -1:
            return None

    # -------------------------------------------------
    # 1) Canonical implication operator
    # -------------------------------------------------
    s = s.replace("=>", "->")

    # -------------------------------------------------
    # 2) Solidity → internal canonical symbols
    # -------------------------------------------------
    s = re.sub(r"\bmsg\.sender\b", "meta.sender", s)
    s = re.sub(r"\bmsg\.value\b", "meta.value", s)

    # ✅ NEW: fix common LLM symbol mistakes for bank contracts
    # The model uses pre.balances/post.balances (plural). LLM sometimes emits singular.
    s = re.sub(r"\bpre\.balance\b", "pre.balances", s)
    s = re.sub(r"\bpost\.balance\b", "post.balances", s)
    s = re.sub(r"\bpre\.bal\b", "pre.balances", s)
    s = re.sub(r"\bpost\.bal\b", "post.balances", s)

    # Normalize boolean literals (keep as "true"/"false" tokens)
    s = re.sub(r"\btrue\b", "true", s, flags=re.I)
    s = re.sub(r"\bfalse\b", "false", s, flags=re.I)

    # -------------------------------------------------
    # 3) Struct / mapping flattening
    #   map[key].field → map_field[key]
    # -------------------------------------------------
    s = _flatten_struct_access(s)

    # -------------------------------------------------
    # 4) Normalize remaining dotted identifiers
    #   a.b → a.b   (keep dot, do NOT underscore)
    # -------------------------------------------------
    # NOTE: dots are part of InvGuard DSL — do NOT replace them

    # -------------------------------------------------
    # 5) Normalize len(x) → x_length
    # -------------------------------------------------
    s = _replace_len(s)

    # -------------------------------------------------
    # 6) Canonical boolean operators
    # -------------------------------------------------
    s = re.sub(r"\bAND\b|\band\b|&&", "&&", s)
    s = re.sub(r"\bOR\b|\bor\b|\|\|", "||", s)
    s = re.sub(r"\bNOT\b|\bnot\b|!", "!", s)

    # -------------------------------------------------
    # 7) Canonical operator spacing
    # -------------------------------------------------
    for op in ["==", "!=", ">=", "<=", ">", "<", "->", "&&", "||"]:
        s = re.sub(rf"\s*{re.escape(op)}\s*", f" {op} ", s)

    # -------------------------------------------------
    # 8) Parenthesis normalization
    # -------------------------------------------------
    s = _repair_parentheses(s)

    # -------------------------------------------------
    # 9) Collapse whitespace (FINAL)
    # -------------------------------------------------
    s = re.sub(r"\s+", " ", s).strip()

    return s or None


# =====================================================
# Helpers
# =====================================================

def _flatten_struct_access(expr: str) -> str:
    """
    map[key].field → map_field[key]
    """
    pattern = r'(\w+)\[([^\]]+)\]\.(\w+)'

    def repl(m):
        return f"{m.group(1)}_{m.group(3)}[{m.group(2)}]"

    return re.sub(pattern, repl, expr)


def _replace_len(expr: str) -> str:
    """
    len(x) → x_length
    """
    return re.sub(r"\blen\(\s*(\w+)\s*\)", r"\1_length", expr)


def _repair_parentheses(expr: str) -> str:
    """
    Ensure balanced parentheses without reordering.
    """
    open_ct = expr.count("(")
    close_ct = expr.count(")")
    if open_ct > close_ct:
        expr = expr + (")" * (open_ct - close_ct))
    return expr
