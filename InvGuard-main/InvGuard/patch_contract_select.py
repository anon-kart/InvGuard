import re

T = "flow_1_files/Z3Checker/cli/driver.py"
src = open(T, encoding="utf-8").read()
if "[patched] contract-aware selection" in src:
    print("already applied"); raise SystemExit

old = """    # 1) Parse Solidity → ContractIR
    cir = SolidityParser().parse(args.sol_file, contract_name=args.contract)

    # 2) Choose function name
    chosen_fn = args.function"""

new = """    # 1) Parse Solidity → ContractIR
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
        _names = _re.findall(r"\\bcontract\\s+([A-Za-z_]\\w*)", _src)
        for _cname in _names:
            try:
                _alt = SolidityParser().parse(args.sol_file, contract_name=_cname)
            except Exception:
                continue
            if any(getattr(fn, "name", None) == chosen_fn
                   for fn in (getattr(_alt, "functions", None) or [])):
                cir = _alt
                break"""

if old not in src:
    print("ANCHOR NOT FOUND — paste driver.py lines 611-617 to me"); raise SystemExit
open(T + ".bak_select", "w", encoding="utf-8").write(src)
open(T, "w", encoding="utf-8").write(src.replace(old, new, 1))
print("[patch] contract-aware selection applied (backup:", T + ".bak_select)")
