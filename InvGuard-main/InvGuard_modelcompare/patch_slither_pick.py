import ast
T = "flow_1_files/Z3Checker/parser/solidity_parser.py"
src = open(T, encoding="utf-8").read()
if "[patched] slither leaf selection" in src:
    print("already applied"); raise SystemExit

old = ("        else:\n"
       "            non_ifaces = [cc for cc in sl.contracts if not cc.is_interface]\n"
       "            c = non_ifaces[0] if non_ifaces else sl.contracts[0]")

new = ('''        else:
            # [patched] slither leaf selection: pick the most-derived concrete
            # contract (the token), not a bundled library/interface such as
            # `contract SafeMath` or `ERC20Interface` that appears first in the file.
            def _is_ifacey(cc):
                if getattr(cc, "is_interface", False):
                    return True
                fns = [f for f in cc.functions if f.is_implemented and len(getattr(f, "nodes", []) or [])]
                return len(fns) == 0
            _concrete = [cc for cc in sl.contracts if not _is_ifacey(cc)]
            _lib_names = {"SafeMath", "SafeERC20", "Address", "Roles", "Math", "Counters"}
            _concrete = [cc for cc in _concrete if cc.name not in _lib_names] or _concrete
            def _impl_fn_count(cc):
                return len([f for f in cc.functions
                            if f.is_implemented and len(getattr(f, "nodes", []) or [])])
            def _derivation(cc):
                return len(getattr(cc, "inheritance", []) or [])
            if _concrete:
                c = sorted(_concrete, key=lambda cc: (_derivation(cc), _impl_fn_count(cc)))[-1]
            else:
                non_ifaces = [cc for cc in sl.contracts if not cc.is_interface]
                c = non_ifaces[0] if non_ifaces else sl.contracts[0]''')

if old not in src:
    print("anchor not found — paste lines 380-384"); raise SystemExit
src = src.replace(old, new, 1)
ast.parse(src)
open(T, "w", encoding="utf-8").write(src)
print("[patch] slither leaf selection applied")
