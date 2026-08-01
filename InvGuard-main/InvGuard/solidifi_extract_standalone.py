#!/usr/bin/env python3
"""
solidifi_extract_standalone.py (v2)
====================================
Extracts each SolidiFI injected target function + ONLY its own state
variables into a standalone contract.

Strict rules:
  - Only declarations (mapping, uint, int, bool, address, bytes, string)
  - Only variables whose name contains the EXACT suffix number
  - Never grabs code statements or variables from other injections
"""
import argparse
import json
import re
from pathlib import Path


# Type keywords that start a state variable declaration
TYPE_KW = r"(?:mapping|uint\d*|int\d*|address|bool|bytes\d*|string)"


def extract_function(source, fn_name):
    """Extract the function body by brace matching."""
    pattern = rf"function\s+{re.escape(fn_name)}\s*\("
    m = re.search(pattern, source)
    if not m:
        return None
    start = m.start()
    depth = 0
    started = False
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
            started = True
        elif source[i] == "}":
            depth -= 1
            if started and depth == 0:
                return source[start:i + 1]
    return None


def get_suffix_id(fn_name):
    """Extract the suffix tag from function name.
    withdraw_balances_re_ent8 -> ('re_ent', '8')
    transfer_intou26 -> ('intou', '26')
    bug_unchk_send15 -> ('unchk_send', '15')
    """
    patterns = [
        (r"_re_ent(\d+)", "re_ent"),
        (r"_intou(\d+)", "intou"),
        (r"_unchk_send(\d+)", "unchk_send"),
        (r"_unchk(\d+)", "unchk"),
        (r"_txorigin(\d+)", "txorigin"),
    ]
    for pat, tag in patterns:
        m = re.search(pat, fn_name)
        if m:
            return tag, m.group(1)
    return None, None


def find_own_state_vars(source, tag, num):
    """Find state variable declarations with the exact suffix.
    For re_ent8: match 'balances_re_ent8', 'counter_re_ent8', etc.
    NOT re_ent13, re_ent20, etc.
    """
    exact_suffix = f"_{tag}{num}"
    declarations = []

    for line in source.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Must start with a type keyword (state variable declaration)
        if not re.match(rf"\s*{TYPE_KW}\b", stripped):
            continue

        # Must contain the exact suffix (word boundary at end)
        if exact_suffix not in stripped:
            continue

        # Must NOT contain function calls or complex expressions
        # A declaration looks like: type [visibility] name [= simple_value];
        if "msg.sender" in stripped or ".call" in stripped or ".send" in stripped:
            continue

        # Must end with ; (possibly with comment)
        if ";" not in stripped:
            continue

        # Clean: take only up to the first ;
        decl = stripped.split(";")[0].strip() + ";"

        # Verify it's plausible: should have the variable name
        if re.search(rf"\w+{re.escape(exact_suffix)}\b", decl):
            declarations.append(decl)

    # Deduplicate
    seen = set()
    unique = []
    for d in declarations:
        if d not in seen:
            seen.add(d)
            unique.append(d)

    return unique


def extract_pragma(source):
    m = re.search(r"(pragma\s+solidity\s+[^;]+;)", source)
    return m.group(1) if m else "pragma solidity >=0.4.22 <0.6.0;"


def build_standalone(source, fn_name, entry):
    fn_body = extract_function(source, fn_name)
    if not fn_body:
        return None, f"function {fn_name} not found"

    tag, num = get_suffix_id(fn_name)
    if not tag or not num:
        return None, f"cannot parse suffix from {fn_name}"

    pragma = extract_pragma(source)
    state_vars = find_own_state_vars(source, tag, num)
    vuln_class = entry["extra_env"].get("INVGUARD_VULN_CLASS", "unknown")

    needs_payable = bool(re.search(
        r"\.call\.value\(|\.send\(|\.transfer\(|msg\.value", fn_body))

    lines = [pragma, "", "contract Target {", ""]

    # State variables for this injection only
    for sv in state_vars:
        lines.append(f"    {sv}")
    if state_vars:
        lines.append("")

    # Owner for tx.origin contracts
    if vuln_class == "tx_origin":
        if not any("owner" in sv for sv in state_vars):
            lines.append("    address public owner;")
            lines.append("")
            lines.append("    constructor() public {")
            lines.append("        owner = msg.sender;")
            lines.append("    }")
            lines.append("")

    # The function itself (indent each line)
    for fl in fn_body.split("\n"):
        lines.append(f"    {fl.rstrip()}")
    lines.append("")

    # Fallback + deposit for payable contracts
    if needs_payable:
        lines.append("    function() external payable {}")
        lines.append("")
        lines.append("    function deposit() public payable {}")
        lines.append("")

    lines.append("}")
    lines.append("")

    return "\n".join(lines), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-dir", default="standalone_contracts")
    ap.add_argument("--out-manifest", default="solidifi_pilot20_standalone.json")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    new_manifest = []
    success = 0

    for entry in manifest:
        stem = entry["stem"]
        sol_path = entry["contract"]
        target_fn = entry["target_function"]

        print(f"  {stem}")
        print(f"    target: {target_fn}")

        source = Path(sol_path).read_text(encoding="utf-8", errors="replace")
        standalone, err = build_standalone(source, target_fn, entry)

        if err:
            print(f"    ERROR: {err}")
            continue

        out_path = out_dir / f"{stem}.sol"
        out_path.write_text(standalone, encoding="utf-8")

        tag, num = get_suffix_id(target_fn)
        state_vars = find_own_state_vars(source, tag, num)
        line_count = standalone.count("\n")
        print(f"    OK: {line_count} lines, {len(state_vars)} state vars")

        new_entry = dict(entry)
        new_entry["contract"] = str(out_path.resolve())
        new_entry["original_contract"] = sol_path
        new_manifest.append(new_entry)
        success += 1

    with open(args.out_manifest, "w") as f:
        json.dump(new_manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Extracted: {success}/{len(manifest)}")
    print(f"  Contracts: {out_dir}/")
    print(f"  Manifest:  {args.out_manifest}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
