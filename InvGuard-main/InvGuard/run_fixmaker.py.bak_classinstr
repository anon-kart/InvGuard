import argparse, asyncio, json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "flow_2_files"))
from agents import Runner
import agent as A

CLASS_INSTR = {
    "reentrancy": "Apply Checks-Effects-Interactions: move ALL state updates BEFORE the external call in {fn}().",
    "integer_overflow": "This is an INTEGER OVERFLOW/UNDERFLOW bug. In {fn}(), add an explicit bound check before writing the arithmetic result (pre-0.8 has no built-in checks), so wrapping reverts. Preserve behavior for non-overflowing inputs.",
    "access_control": "This is an ACCESS-CONTROL bug. Add an authorization check at the START of {fn}(): require(msg.sender == owner) (or the contract's existing privileged address such as creator/admin). If {fn} sets a privileged address with no check, restrict it so only the current privileged address (or one-time uninitialized state) may call it.",
    "tx_origin": "This is a tx.origin AUTHENTICATION bug. Replace every `tx.origin == <owner>` check in {fn}() with `msg.sender == <owner>`. Change nothing else.",
    "unchecked_call": "This is an UNCHECKED-CALL bug. The low-level call/send return value in {fn}() is ignored. Require success: (bool ok,) = x.call.value(v)(\"\"); require(ok); so a failed transfer reverts instead of being silently ignored.",
}

def load_invariants(stem_dir, target_fn):
    d = Path(stem_dir) / "flow1_outputs"
    for pat in (f"verified_invariants.{target_fn}.txt", "verified_invariants.*.txt"):
        for f in sorted(d.glob(pat)):
            if any(x in f.name for x in (".unknown.", ".rejected.", ".unsound.", ".weak.")):
                continue
            lines = [l for l in f.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
            if lines:
                return "\n".join(lines)
    return "(no verified invariants)"

async def one(contract_path, target_fn, vclass, stem_dir, out_path):
    src = Path(contract_path).read_text()
    cname_m = re.search(r"contract\s+(\w+)\s*\{", src)
    cname = cname_m.group(1) if cname_m else "UnknownContract"
    fn_sigs = re.findall(r"function\s+\w+\s*\([^)]*\)[^{;]*", src)
    inv = load_invariants(stem_dir, target_fn)
    instr = CLASS_INSTR.get(vclass, CLASS_INSTR["reentrancy"]).format(fn=target_fn)

    fix_query = f"""
You MUST patch the EXACT contract below. Do NOT write a new or different contract.
Do NOT rename any functions, state variables, or the contract itself.
Fix the {target_fn}() function as follows: {instr}
Everything else stays identical.

CONTRACT_NAME: {cname}
TARGET_FUNCTION_TO_FIX: {target_fn}
FUNCTION_SIGNATURES_TO_PRESERVE: {'; '.join(fn_sigs[:6])}

INVARIANTS_START
{inv}
INVARIANTS_END

ATTACKS_START
[]
ATTACKS_END

THE EXACT CONTRACT TO PATCH (output this contract with ONLY {target_fn} fixed):
SMART_CONTRACT_START
{src}
SMART_CONTRACT_END
"""
    class _Ctx:
        pass
    out = await Runner.run(A.fix_maker_agent, fix_query, context=_Ctx(), max_turns=20)
    fixed, desc = A._extract_fixed_contract_and_desc(out.final_output)
    if not fixed or "contract " not in fixed:
        print(f"FIXMAKER_FAIL {out_path.name}: no valid contract block")
        Path(out_path).with_suffix(".raw.txt").write_text(out.final_output or "")
        return
    Path(out_path).write_text(fixed)
    print(f"FIXMAKER_OK {out_path.name}: {desc[:80]}")

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="json: [[contract_path,target_fn,vclass,stem_dir,out_path],...]")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    for row in spec:
        try:
            await one(*[*row[:4], Path(row[4])])
        except Exception as e:
            print(f"FIXMAKER_ERR {row[4]}: {str(e)[:160]}")

if __name__ == "__main__":
    asyncio.run(main())
