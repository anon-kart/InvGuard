import asyncio, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "flow_2_files"))
from agents import Runner
import agent as A

AC_INSTR = ("This is an ACCESS-CONTROL bug. Restrict {fn}() so only the legitimate privileged "
  "address may cause the privileged effect. If the contract has no initialized privileged "
  "address, establish one (e.g. set it in the constructor, or allow a one-time initialization "
  "when it is still unset). CRITICAL: after the fix, {fn}() MUST remain callable by the "
  "legitimate user; do not make it uncallable.")

ITEMS = [
  ("ac_wallet03", "wallet_03_wrong_constructor.sol", "initWallet",
   "A previous patch guarded initWallet() with require(msg.sender == creator). On the exploit "
   "harness this made initWallet() UNCALLABLE: creator is never set before the first call, so "
   "every legitimate initialization reverts and the wallet can never be used (functional check "
   "FAILED). A correct repair must (a) stop an attacker re-initializing/hijacking the wallet once "
   "set, and (b) still allow a legitimate one-time initialization to succeed."),
  ("ac_mapwrite", "mapping_write.sol", "set",
   "A previous patch guarded set() with require(msg.sender == owner). On the exploit harness this "
   "made set() PERMANENTLY UNCALLABLE: owner is declared but never assigned (no constructor or "
   "setter), so it stays the zero address and no caller passes the check (functional check FAILED). "
   "A correct repair must (a) prevent unauthorized/arbitrary storage writes, and (b) keep set() "
   "usable by the legitimate owner, which requires establishing who the owner is."),
]

async def one(stem, fname, fn, feedback, out):
    AC = Path.home()/ "Downloads/sb-heists/smartbugs-curated/0.4.x/contracts/dataset/access_control"
    src = (AC/fname).read_text()
    m = re.search(r"contract\s+(\w+)\s*\{", src); cname = m.group(1) if m else "Unknown"
    fn_sigs = re.findall(r"function\s+\w+\s*\([^)]*\)[^{;]*", src)
    fix_query = f"""You MUST patch the EXACT contract below. Do NOT write a new or different contract.
Do NOT rename any functions, state variables, or the contract itself.
Fix the {fn}() function as follows: {AC_INSTR.format(fn=fn)}
Everything else stays identical.

CONTRACT_NAME: {cname}
TARGET_FUNCTION_TO_FIX: {fn}
FUNCTION_SIGNATURES_TO_PRESERVE: {'; '.join(fn_sigs[:6])}

PATCH_FEEDBACK_START
{feedback}
PATCH_FEEDBACK_END

INVARIANTS_START
(no verified invariants)
INVARIANTS_END

ATTACKS_START
[]
ATTACKS_END

THE EXACT CONTRACT TO PATCH (output this contract with ONLY {fn} fixed):
SMART_CONTRACT_START
{src}
SMART_CONTRACT_END
"""
    class C: pass
    o = await Runner.run(A.fix_maker_agent, fix_query, context=C(), max_turns=20)
    fixed, desc = A._extract_fixed_contract_and_desc(o.final_output)
    if not fixed or "contract " not in fixed:
        print(f"P2_FAIL {stem}"); Path(str(out)+".raw.txt").write_text(o.final_output or ""); return
    Path(out).write_text(fixed); print(f"P2_OK {stem}: {desc[:90]}")

async def main():
    REPO = Path(__file__).parent
    for stem,fname,fn,fb in ITEMS:
        await one(stem, fname, fn, fb, REPO/"patches"/f"{stem}_p2.sol")

if __name__ == "__main__":
    asyncio.run(main())
