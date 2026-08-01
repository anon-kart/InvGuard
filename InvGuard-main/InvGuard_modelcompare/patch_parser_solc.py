import re
T = "flow_1_files/Z3Checker/parser/solidity_parser.py"
src = open(T, encoding="utf-8").read()
if "[patched] bind solc" in src:
    print("already applied"); raise SystemExit

m = re.search(r"^([ \t]*)def parse\(self, filepath[^\n]*:\n", src, flags=re.M)
if not m:
    print("parse() not found"); raise SystemExit
indent = m.group(1) + "    "
inject = (
    f"{indent}# [patched] bind solc to the file's pragma before any compile\n"
    f"{indent}try:\n"
    f"{indent}    import os as _os, sys as _sys\n"
    f"{indent}    _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))\n"
    f"{indent}    if _root not in _sys.path: _sys.path.insert(0, _root)\n"
    f"{indent}    from solc_path_fix import ensure_solc_on_path_for as _bind\n"
    f"{indent}    _bind(filepath)\n"
    f"{indent}except Exception:\n"
    f"{indent}    pass\n"
)
# insert right after the def line
pos = m.end()
open(T + ".bak_solcbind", "w", encoding="utf-8").write(src)
new = src[:pos] + inject + src[pos:]
open(T, "w", encoding="utf-8").write(new)
import ast; ast.parse(open(T, encoding="utf-8").read())
print("[patch] bind solc injected into parse(); file parses OK")
