import sys
from pathlib import Path

DEFAULT = "flow_2_files/agent.py"

OLD = '''    if not text:
        return "", ""

    m = re.search(r"FIXED_CONTRACT_START(.*?)FIXED_CONTRACT_END", text, re.S)
    if m:
        contract = m.group(1).strip()

    # Strip markdown fences if the model included them
    contract = re.sub(r"^\\s*```[a-zA-Z]*\\s*", "", contract)
    contract = re.sub(r"\\s*```\\s*$", "", contract).strip()'''

NEW = '''    if not text:
        return "", ""

    marker_pairs = [
        (r"FIXED_CONTRACT_START", r"FIXED_CONTRACT_END"),
        (r"FIXED_CONTRACT_START", r"SMART_CONTRACT_END"),
        (r"SMART_CONTRACT_START", r"SMART_CONTRACT_END"),
    ]
    for start, end in marker_pairs:
        for m in re.finditer(start + r"(.*?)" + end, text, re.S):
            block = m.group(1).strip()
            if "contract " in block:
                contract = block
        if contract:
            break

    if not contract:
        m = re.search(r"FIXED_CONTRACT_START(.*)$", text, re.S) or \\
            re.search(r"SMART_CONTRACT_START(.*)$", text, re.S)
        if m and "contract " in m.group(1):
            contract = re.split(r"FIX_DESCRIPTION:", m.group(1))[0].strip()

    contract = re.sub(r"^\\s*```[a-zA-Z]*\\s*", "", contract)
    contract = re.sub(r"\\s*```\\s*$", "", contract).strip()'''


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT)
    src = target.read_text()
    if "marker_pairs = [" in src:
        print(f"already patched: {target}")
        return
    if OLD not in src:
        print(f"ERROR: original block not found in {target} (manual edit needed)")
        sys.exit(1)
    target.with_suffix(target.suffix + ".bak_extractor").write_text(src)
    target.write_text(src.replace(OLD, NEW))
    print(f"patched: {target} (backup at {target}.bak_extractor)")


if __name__ == "__main__":
    main()
