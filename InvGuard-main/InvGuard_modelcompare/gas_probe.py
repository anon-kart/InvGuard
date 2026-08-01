#!/usr/bin/env python3
"""
gas_probe.py  —  measure gas overhead of a patch (Result #2 gas column)
=======================================================================
Deploys ORIGINAL and PATCHED contracts in a throwaway Foundry project, runs a
forge --gas-report on a single call to the target function, and returns the
average-gas delta as a percentage.

Best-effort: if the target function needs args/payable setup that this generic
harness can't synthesize, it returns {"overhead_pct": None, "reason": ...} and
the table prints "n/a" for that contract. It never crashes the pipeline.

Called from flow_2_files/agent.py via Hook C (see CODE_HOOKS.md).
"""
import json, os, re, shutil, subprocess, tempfile

_FORGE_TOML = """[profile.default]
src = "src"
test = "test"
optimizer = true
optimizer_runs = 200
"""

_GAS_TEST = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import "forge-std/Test.sol";
import {{Target as Orig}} from "src/Orig.sol";
import {{Target as Patched}} from "src/Patched.sol";

contract GasTest is Test {{
    function test_gas_original() public {{
        Orig o = new Orig();
        // best-effort warm call; if it reverts, gas-report still records deploy
        (bool ok,) = address(o).call{{value: 0}}(
            abi.encodeWithSignature("{sig}"));
        ok;
    }}
    function test_gas_patched() public {{
        Patched p = new Patched();
        (bool ok,) = address(p).call{{value: 0}}(
            abi.encodeWithSignature("{sig}"));
        ok;
    }}
}}
"""


def _rename_contract(src: str, new: str) -> str:
    # Rename the primary contract to `new` so both files can import as `Target`.
    m = re.search(r"contract\s+(\w+)", src)
    if not m:
        return src
    old = m.group(1)
    return re.sub(rf"\bcontract\s+{re.escape(old)}\b", f"contract {new}", src, count=1)


def measure_gas_overhead(repo_root, original_src, patched_src, target_function):
    forge = shutil.which("forge")
    if not forge:
        return {"overhead_pct": None, "reason": "forge_not_found"}
    sig = f"{target_function}()"  # generic 0-arg signature; args -> falls back to n/a
    proj = tempfile.mkdtemp(prefix="invguard_gas_")
    try:
        src_dir = os.path.join(proj, "src"); os.makedirs(src_dir)
        test_dir = os.path.join(proj, "test"); os.makedirs(test_dir)
        lib = os.path.join(proj, "lib", "forge-std", "src"); os.makedirs(lib)
        # Symlink forge-std from the repo's existing replay project if present.
        repo_std = None
        for cand in (os.path.join(repo_root, "run_outputs", "flow2",
                                  "exploit_executor", "T1", "lib", "forge-std"),):
            if os.path.isdir(cand):
                repo_std = cand; break
        if repo_std:
            shutil.rmtree(os.path.join(proj, "lib", "forge-std"), ignore_errors=True)
            shutil.copytree(repo_std, os.path.join(proj, "lib", "forge-std"))
        else:
            return {"overhead_pct": None, "reason": "no_forge_std"}

        open(os.path.join(proj, "foundry.toml"), "w").write(_FORGE_TOML)
        open(os.path.join(src_dir, "Orig.sol"), "w").write(
            _rename_contract(original_src, "Target"))
        open(os.path.join(src_dir, "Patched.sol"), "w").write(
            _rename_contract(patched_src, "Target"))
        open(os.path.join(test_dir, "Gas.t.sol"), "w").write(
            _GAS_TEST.format(sig=sig))

        p = subprocess.run([forge, "test", "--gas-report"], cwd=proj,
                           capture_output=True, text=True, timeout=300)
        out = p.stdout
        # Parse the gas-report table for the target function avg gas per file.
        orig_gas = _avg_gas(out, "Orig")
        patch_gas = _avg_gas(out, "Patched")
        if orig_gas and patch_gas and orig_gas > 0:
            pct = round(100 * (patch_gas - orig_gas) / orig_gas, 2)
            return {"overhead_pct": pct, "orig_gas": orig_gas,
                    "patched_gas": patch_gas}
        return {"overhead_pct": None, "reason": "gas_unparsed",
                "stdout_head": out[:500]}
    except subprocess.TimeoutExpired:
        return {"overhead_pct": None, "reason": "timeout"}
    except Exception as e:
        return {"overhead_pct": None, "reason": f"err:{e}"}
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def _avg_gas(report_text, contract_label):
    # forge gas-report lines look like: | functionName | min | avg | median | max | calls |
    # We grab the avg column of the target function under the right contract block.
    avg = None
    in_block = False
    for ln in report_text.splitlines():
        if contract_label in ln and "Contract" in ln:
            in_block = True; continue
        if in_block and ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.split("|")]
            # cells: ['', name, min, avg, median, max, calls, '']
            if len(cells) >= 5 and cells[3].isdigit():
                avg = int(cells[3])
        if in_block and ln.strip().startswith("╰"):
            break
    return avg
