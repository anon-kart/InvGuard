import re, ast
T = "flow_1_files/Z3Checker/parser/solidity_parser.py"
src = open(T, encoding="utf-8").read()
changed = []

# ---- FIX 1: skip unimplemented / interface function bodies in the Slither loop ----
if "[patched] skip unimplemented fn" not in src:
    anchor = "        for f in c.functions:\n            if f.is_constructor or f.is_fallback or f.is_receive:\n                continue"
    if anchor not in src:
        print("FIX1 anchor not found"); raise SystemExit
    repl = ("        # [patched] skip unimplemented fn: prefer the concrete override\n"
            "        # over an inherited interface/abstract signature with an empty body.\n"
            "        _seen_impl = {}\n"
            "        for _f in c.functions:\n"
            "            if getattr(_f, 'is_implemented', None) and len(getattr(_f, 'nodes', []) or []):\n"
            "                _seen_impl[_f.name] = _f\n"
            "        for f in c.functions:\n"
            "            if f.is_constructor or f.is_fallback or f.is_receive:\n"
            "                continue\n"
            "            if f.name in _seen_impl and _seen_impl[f.name] is not f:\n"
            "                continue\n"
            "            if not (getattr(f, 'is_implemented', None) and len(getattr(f, 'nodes', []) or [])):\n"
            "                if f.name in _seen_impl:\n"
            "                    continue")
    src = src.replace(anchor, repl, 1)
    changed.append("FIX1 skip-unimplemented")

# ---- FIX 2: SafeMath lowering in _coarse_stmt_from_line (before store_map) ----
if "[patched] SafeMath lowering" not in src:
    anchor2 = ("        # ---- mapping store: x[key] = val ----")
    if anchor2 not in src:
        print("FIX2 anchor not found"); raise SystemExit
    inject = '''        # [patched] SafeMath lowering: x[key] = safeSub/safeAdd(x[key], v)  -> map_sub/map_add
        m = re.match(
            r"^([A-Za-z_]\\w*)\\s*\\[(.+?)\\]\\s*=\\s*(?:safeSub|sub|safeAdd|add)\\s*\\(\\s*\\1\\s*\\[\\s*(?:.+?)\\s*\\]\\s*,\\s*(.+)\\)\\s*$",
            line,
        )
        if m:
            _is_add = bool(re.search(r"=\\s*(?:safeAdd|add)\\s*\\(", line))
            return {
                "op": "map_add" if _is_add else "map_sub",
                "map": m.group(1).strip(),
                "key_src": _normalize_key_src(m.group(2)),
                "val_src": _normalize_expr_src(m.group(3)),
            }
        # [patched] SafeMath lowering (member form): x[key] = x[key].sub(v)/.add(v)
        m = re.match(
            r"^([A-Za-z_]\\w*)\\s*\\[(.+?)\\]\\s*=\\s*\\1\\s*\\[\\s*(?:.+?)\\s*\\]\\s*\\.\\s*(sub|add)\\s*\\(\\s*(.+)\\)\\s*$",
            line,
        )
        if m:
            return {
                "op": "map_add" if m.group(3) == "add" else "map_sub",
                "map": m.group(1).strip(),
                "key_src": _normalize_key_src(m.group(2)),
                "val_src": _normalize_expr_src(m.group(4)),
            }
        # [patched] SafeMath lowering (scalar): x = safeSub/safeAdd(x, v) -> store_sub/store_add
        m = re.match(
            r"^([A-Za-z_]\\w*)\\s*=\\s*(?:safeSub|sub|safeAdd|add)\\s*\\(\\s*\\1\\s*,\\s*(.+)\\)\\s*$",
            line,
        )
        if m:
            _is_add = bool(re.search(r"=\\s*(?:safeAdd|add)\\s*\\(", line))
            return {
                "op": "store_add" if _is_add else "store_sub",
                "var": _normalize_var_name(m.group(1)),
                "val_src": _normalize_expr_src(m.group(2)),
            }
'''
    src = src.replace(anchor2, inject + anchor2, 1)
    changed.append("FIX2 safemath-lowering")

if not changed:
    print("nothing to do (already applied)"); raise SystemExit
open(T + ".bak_safemath", "w", encoding="utf-8").write(open(T, encoding="utf-8").read()) if False else None
ast.parse(src)
open(T + ".bak_safemath", "w", encoding="utf-8").write(open(T).read()) if False else None
open(T, "w", encoding="utf-8").write(src)
print("[patch] applied:", ", ".join(changed))
