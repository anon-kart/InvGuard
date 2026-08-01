import ast
T = "flow_1_files/Z3Checker/parser/solidity_parser.py"
src = open(T, encoding="utf-8").read()
if "[patched] flatten inheritance vars" in src:
    print("already applied"); raise SystemExit

old = ("        # [patched] inherited state vars: include base-contract state\n"
       "        _svs = getattr(c, 'state_variables', None) or c.state_variables_declared\n"
       "        for sv in _svs:")

new = ('''        # [patched] flatten inheritance vars: Slither drops PRIVATE vars from a
        # derived contract's state_variables, so walk the whole inheritance chain
        # and union each contract's *declared* vars (private included).
        _seen_names = set()
        _svs = []
        _chain = [c] + list(getattr(c, "inheritance", []) or [])
        for _cc in _chain:
            for _sv in getattr(_cc, "state_variables_declared", []) or []:
                if _sv.name not in _seen_names:
                    _seen_names.add(_sv.name)
                    _svs.append(_sv)
        if not _svs:
            _svs = getattr(c, "state_variables", None) or c.state_variables_declared
        for sv in _svs:''')

if old not in src:
    print("anchor not found — the earlier inherited-state patch block moved; paste it to me"); raise SystemExit
src = src.replace(old, new, 1)
ast.parse(src)
open(T, "w", encoding="utf-8").write(src)
print("[patch] flatten inheritance vars applied")
