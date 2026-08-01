import sys
from pathlib import Path

TARGET = "flow_1_files/agent.py"

INSTR_OLD = '        "After saving invariants, you MUST hand off to z3_checker_agent.\\n"\n'
INSTR_NEW = '        "After saving invariants, stop. The Z3 checker runs automatically afterward.\\n"\n'

HANDOFF_OLD = 'invariant_generating_agent.handoffs = [handoff(agent=z3_checker_agent)]\n'
HANDOFF_NEW = 'invariant_generating_agent.handoffs = []\n'


def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(TARGET)
    src = p.read_text()
    if "invariant_generating_agent.handoffs = []" in src:
        print(f"already patched: {p}")
        return
    for old in (INSTR_OLD, HANDOFF_OLD):
        if old not in src:
            print(f"ERROR: anchor not found in {p}:\n{old!r}")
            sys.exit(1)
    p.with_suffix(p.suffix + ".bak_splitagent").write_text(src)
    src = src.replace(INSTR_OLD, INSTR_NEW, 1).replace(HANDOFF_OLD, HANDOFF_NEW, 1)
    p.write_text(src)
    print(f"patched: {p}")


if __name__ == "__main__":
    main()
