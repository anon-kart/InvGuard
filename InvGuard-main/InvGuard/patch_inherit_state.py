import ast
T = "flow_1_files/Z3Checker/parser/solidity_parser.py"
src = open(T, encoding="utf-8").read()
if "[patched] inherited state vars" in src:
    print("already applied"); raise SystemExit
old = "        state: List[VarDecl] = []\n\n        for sv in c.state_variables_declared:"
new = ("        state: List[VarDecl] = []\n\n"
       "        # [patched] inherited state vars: include base-contract state\n"
       "        _svs = getattr(c, 'state_variables', None) or c.state_variables_declared\n"
       "        for sv in _svs:")
if old not in src:
    print("anchor not found — paste lines around 'for sv in c.state_variables_declared'"); raise SystemExit
src = src.replace(old, new, 1)
ast.parse(src)
open(T, "w", encoding="utf-8").write(src)
print("[patch] inherited state vars applied")
