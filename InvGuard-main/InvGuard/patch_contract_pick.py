import re
T = "flow_1_files/Z3Checker/parser/solidity_parser.py"
src = open(T, encoding="utf-8").read()
if "[patched] skip-interface selection" in src:
    print("already applied"); raise SystemExit

# match: <indent>cnode = contracts[0]
m = re.search(r"^([ \t]*)cnode = contracts\[0\]\s*$", src, flags=re.M)
if not m:
    print("STILL NOT FOUND — paste the cat -A output"); raise SystemExit
indent = m.group(1)

repl = (
    f"{indent}# [patched] skip-interface selection\n"
    f"{indent}def _has_fns(_n):\n"
    f"{indent}    return any(_x.get('nodeType') == 'FunctionDefinition' and _x.get('body') is not None\n"
    f"{indent}               for _x in _n.get('nodes', []))\n"
    f"{indent}def _is_iface(_n):\n"
    f"{indent}    return _n.get('contractKind') == 'interface' or _n.get('abstract', False)\n"
    f"{indent}_concrete = [_n for _n in contracts if not _is_iface(_n) and _has_fns(_n)]\n"
    f"{indent}if _concrete:\n"
    f"{indent}    cnode = _concrete[-1]\n"
    f"{indent}else:\n"
    f"{indent}    _noniface = [_n for _n in contracts if not _is_iface(_n)]\n"
    f"{indent}    cnode = (_noniface or contracts)[-1]"
)

open(T + ".bak_pick", "w", encoding="utf-8").write(src)
new_src = src[:m.start()] + repl + src[m.end():]
open(T, "w", encoding="utf-8").write(new_src)
# sanity: file still parses
import ast
ast.parse(open(T, encoding="utf-8").read())
print("[patch] skip-interface selection applied (indent-safe); file parses OK")
