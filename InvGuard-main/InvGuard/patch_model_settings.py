import sys
from pathlib import Path

HELPER = '''def _msettings(**kw):
    _m = os.environ.get("INVGUARD_MODEL", "gpt-4o-mini").lower()
    if _m.startswith(("gpt-5", "o1", "o3", "o4")):
        kw.pop("temperature", None)
        kw.pop("top_p", None)
    return ModelSettings(**kw)'''

DET_OLD = 'DETERMINISTIC = ModelSettings(temperature=0.0, top_p=1.0)'
DET_NEW = HELPER + '\n\nDETERMINISTIC = _msettings(temperature=0.0, top_p=1.0)'

FC_OLD = ('fix_checker_agent.model_settings = ModelSettings(\n'
          '    temperature=0.0, top_p=1.0, tool_choice="auto"\n)')
FC_NEW = 'fix_checker_agent.model_settings = _msettings(temperature=0.0, top_p=1.0, tool_choice="auto")'


def patch(path, do_fixchecker=False):
    p = Path(path)
    src = p.read_text()
    if "_msettings" in src:
        print(f"already patched: {path}")
        return
    if DET_OLD not in src:
        print(f"ERROR: settings line not found in {path}")
        sys.exit(1)
    new = src.replace(DET_OLD, DET_NEW, 1)
    if do_fixchecker:
        if FC_OLD not in new:
            print(f"ERROR: fix_checker settings not found in {path}")
            sys.exit(1)
        new = new.replace(FC_OLD, FC_NEW, 1)
    p.with_suffix(p.suffix + ".bak_msettings").write_text(src)
    p.write_text(new)
    print(f"patched: {path}")


if __name__ == "__main__":
    patch("flow_1_files/agent.py")
    patch("flow_2_files/agent.py", do_fixchecker=True)
