import sys
from pathlib import Path

TARGET = "flow_1_files/agent.py"

ANCHOR = ('            "deterministic generation will supply/repair them.",\n'
          '            _have_contract, _have_invs,\n'
          '        )\n')

BLOCK = '''
    # --- tool-call recovery: some models (e.g. reasoning models) skip save_invariants;
    # salvage invariant predicates from the agent's final text so the checker can run.
    # Applies to all models; a no-op when invariants.txt already exists.
    if _have_contract and not _have_invs and _agent_ok:
        try:
            _txt = str(getattr(_agent_result, "final_output", "") or "")
            _cand = []
            for _ln in _txt.splitlines():
                _s = _ln.strip().lstrip("-*0123456789. ").strip()
                if not _s or _s.startswith(("#", "//")):
                    continue
                if any(_op in _s for _op in ("==", "<=", ">=", "!=", "=>", "->", "&&", "||", "<", ">")):
                    _cand.append(_s)
            if _cand:
                save_invariants(_cand)
                _have_invs = _artifact_present("invariants.txt")
                logging.info("[FLOW1] recovered %d invariant(s) from final text (save_invariants skipped).", len(_cand))
            else:
                logging.info("[FLOW1] no invariant-like lines in final text; nothing to recover.")
        except Exception as _rec_exc:
            logging.warning("[FLOW1] invariant recovery failed: %s", _rec_exc)
'''


def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(TARGET)
    src = p.read_text()
    if "tool-call recovery" in src:
        print(f"already patched: {p}")
        return
    if ANCHOR not in src:
        print(f"ERROR: anchor not found in {p}")
        sys.exit(1)
    p.with_suffix(p.suffix + ".bak_invrecovery").write_text(src)
    p.write_text(src.replace(ANCHOR, ANCHOR + BLOCK, 1))
    print(f"patched: {p}")


if __name__ == "__main__":
    main()
