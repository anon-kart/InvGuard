import argparse, asyncio, json, re, sys
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


GENERIC_INSTR = {
    "reentrancy": "This contract has a reentrancy vulnerability. Apply Checks-Effects-Interactions: move all state updates before the external call in the affected function.",
    "integer_overflow": "This contract has an integer overflow/underflow vulnerability. Add an explicit bound check before the arithmetic result is written (pre-0.8 has no built-in checks), so wrapping reverts.",
    "access_control": "This contract has an access-control vulnerability. Add an authorization check to the unprotected privileged function so only the legitimate owner/privileged address can call it.",
    "tx_origin": "This contract has a tx.origin authentication vulnerability. Replace tx.origin with msg.sender in the authentication check.",
    "unchecked_call": "This contract has an unchecked low-level call whose return value is ignored. Require the call's success so a failed transfer reverts instead of being silently ignored.",
}


def _read_lines(f):
    return [l for l in f.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]


def load_invariants(stem_dir, target_fn, config):
    d = Path(stem_dir) / "flow1_outputs"
    if config == "direct_llm":
        return "(no verified invariants)"
    if config == "no_smt":
        for pat in (f"invariants.forced.{target_fn}.filtered.txt",
                    "invariants.forced.*.filtered.txt", "invariants.txt"):
            for f in sorted(d.glob(pat)):
                lines = _read_lines(f)
                if lines:
                    return "\n".join(lines)
        return "(no verified invariants)"
    for pat in (f"verified_invariants.{target_fn}.txt", "verified_invariants.*.txt"):
        for f in sorted(d.glob(pat)):
            if any(x in f.name for x in (".unknown.", ".rejected.", ".unsound.", ".weak.")):
                continue
            lines = _read_lines(f)
            if lines:
                return "\n".join(lines)
    return "(no verified invariants)"


async def one(contract_path, target_fn, vclass, stem_dir, out_path, config, targeting, feedback=""):
    src = Path(contract_path).read_text()
    cname_m = re.search(r"contract\s+(\w+)\s*\{", src)
    cname = cname_m.group(1) if cname_m else "UnknownContract"
    fn_sigs = re.findall(r"function\s+\w+\s*\([^)]*\)[^{;]*", src)
    inv = load_invariants(stem_dir, target_fn, config)

    if targeting == "untargeted":
        instr = GENERIC_INSTR.get(vclass, GENERIC_INSTR["reentrancy"])
        head = (f"Fix the vulnerability as follows: {instr}\n"
                f"Locate the vulnerable function yourself. Everything else stays identical.\n\n"
                f"CONTRACT_NAME: {cname}\n"
                f"FUNCTION_SIGNATURES_TO_PRESERVE: {'; '.join(fn_sigs[:8])}")
        tail = "output this contract with the vulnerability fixed"
    else:
        instr = CLASS_INSTR.get(vclass, CLASS_INSTR["reentrancy"]).format(fn=target_fn)
        head = (f"Fix the {target_fn}() function as follows: {instr}\n"
                f"Everything else stays identical.\n\n"
                f"CONTRACT_NAME: {cname}\n"
                f"TARGET_FUNCTION_TO_FIX: {target_fn}\n"
                f"FUNCTION_SIGNATURES_TO_PRESERVE: {'; '.join(fn_sigs[:6])}")
        tail = f"output this contract with ONLY {target_fn} fixed"

    fb = f"\nPATCH_FEEDBACK_START\n{feedback}\nPATCH_FEEDBACK_END\n" if feedback else ""

    fix_query = f"""
You MUST patch the EXACT contract below. Do NOT write a new or different contract.
Do NOT rename any functions, state variables, or the contract itself.
{head}
{fb}
INVARIANTS_START
{inv}
INVARIANTS_END

ATTACKS_START
[]
ATTACKS_END

THE EXACT CONTRACT TO PATCH ({tail}):
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
    print(f"FIXMAKER_OK [{config}/{targeting}] {out_path.name}: {desc[:80]}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--config", required=True, choices=["full", "no_smt", "direct_llm"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--targeting", default="targeted", choices=["targeted", "untargeted"])
    ap.add_argument("--feedback-dir", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--repo", default=str(Path(__file__).parent))
    a = ap.parse_args()

    manifest = json.loads(Path(a.manifest).read_text())
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fbdir = Path(a.feedback_dir) if a.feedback_dir else None
    only = set(s for s in a.only.split(",") if s) or None

    for row in manifest:
        stem = row["stem"]
        if only and stem not in only:
            continue
        vclass = row.get("extra_env", {}).get("INVGUARD_VULN_CLASS", "reentrancy")
        stem_dir = Path(a.repo) / "results" / a.tag / stem
        out_path = outdir / f"{stem}.sol"
        feedback = ""
        if fbdir and (fbdir / f"{stem}.txt").is_file():
            feedback = (fbdir / f"{stem}.txt").read_text().strip()
        try:
            await one(row["contract"], row["target_function"], vclass, stem_dir,
                      out_path, a.config, a.targeting, feedback)
        except Exception as e:
            print(f"FIXMAKER_ERR {stem}: {str(e)[:160]}")


if __name__ == "__main__":
    asyncio.run(main())
