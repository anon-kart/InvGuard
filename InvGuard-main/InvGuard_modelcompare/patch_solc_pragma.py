#!/usr/bin/env python3
import os, re, shutil, sys

TARGET = os.path.join("flow_1_files", "Z3Checker", "parser", "solidity_parser.py")
MARKER = "# [patched] full 0.4-0.8 pragma resolution"

NEW_METHOD = '''    def _infer_solc_version_from_pragma(self, src: str) -> Optional[str]:
        # [patched] full 0.4-0.8 pragma resolution
        m = re.search(r"pragma\\s+solidity\\s+([^;]+);", src)
        if not m:
            return None
        spec = m.group(1).strip()

        triple = re.search(r"(\\d+)\\.(\\d+)\\.(\\d+)", spec)
        pair = re.search(r"(\\d+)\\.(\\d+)", spec)
        if triple:
            major, minor, patch = (int(triple.group(1)), int(triple.group(2)),
                                   int(triple.group(3)))
        elif pair:
            major, minor, patch = int(pair.group(1)), int(pair.group(2)), None
        else:
            return None

        exact = not any(c in spec for c in ("^", "~", ">", "<"))

        defaults = {
            (0, 4): "0.4.26", (0, 5): "0.5.17", (0, 6): "0.6.12",
            (0, 7): "0.7.6", (0, 8): "0.8.26",
        }

        try:
            import solcx as _scx
            installed = [str(v).lstrip("v") for v in
                         _scx.get_installed_solc_versions()]
        except Exception:
            _scx = None
            installed = []

        if exact and patch is not None:
            ver = f"{major}.{minor}.{patch}"
        else:
            same_minor = [iv for iv in installed
                          if iv.startswith(f"{major}.{minor}.")]
            if same_minor:
                ver = sorted(same_minor,
                             key=lambda s: list(map(int, s.split("."))))[-1]
            else:
                ver = defaults.get((major, minor))

        if ver and _scx is not None and not any(ver in iv for iv in installed):
            try:
                _scx.install_solc(ver)
            except Exception:
                pass
        return ver
'''

def main():
    if not os.path.isfile(TARGET):
        sys.exit(f"cannot find {TARGET}; run from the InvGuard repo root")
    src = open(TARGET, encoding="utf-8").read()
    if MARKER in src:
        print("[patch] already applied; nothing to do"); return
    pat = re.compile(
        r"    def _infer_solc_version_from_pragma\(self, src[^\n]*\).*?(?=\n    def )",
        re.DOTALL)
    if not pat.search(src):
        sys.exit("[patch] could not locate _infer_solc_version_from_pragma; patch manually.")
    shutil.copy2(TARGET, TARGET + ".bak_solc")
    new_src = pat.sub(lambda _m: NEW_METHOD.rstrip("\n"), src, count=1)
    open(TARGET, "w", encoding="utf-8").write(new_src)
    print(f"[patch] updated {TARGET} (backup: {TARGET}.bak_solc)")

if __name__ == "__main__":
    main()
