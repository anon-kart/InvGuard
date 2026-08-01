import os, re, glob

def _installed():
    d = os.path.expanduser("~/.solcx")
    out = {}
    for p in glob.glob(os.path.join(d, "solc-v*")):
        m = re.search(r"solc-v(\d+)\.(\d+)\.(\d+)$", p)
        if m and os.access(p, os.X_OK):
            out[(int(m[1]), int(m[2]), int(m[3]))] = p
    return out

def _resolve(spec, inst):
    tri = re.search(r"(\d+)\.(\d+)\.(\d+)", spec)
    pair = re.search(r"(\d+)\.(\d+)", spec)
    if tri:
        maj, minr, pat = int(tri[1]), int(tri[2]), int(tri[3])
    elif pair:
        maj, minr, pat = int(pair[1]), int(pair[2]), None
    else:
        return None
    exact = not any(c in spec for c in "^~><")
    if exact and pat is not None and (maj, minr, pat) in inst:
        return inst[(maj, minr, pat)]
    same = sorted([k for k in inst if k[0] == maj and k[1] == minr])
    return inst[same[-1]] if same else None

def ensure_solc_on_path_for(sol_file):
    try:
        src = open(sol_file, encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    m = re.search(r"pragma\s+solidity\s+([^;]+);", src)
    if not m:
        return None
    binpath = _resolve(m.group(1), _installed())
    if not binpath:
        return None
    shim = os.path.join("/tmp", "invguard_solc_shim")
    os.makedirs(shim, exist_ok=True)
    link = os.path.join(shim, "solc")
    try:
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link)
        os.symlink(binpath, link)
    except Exception:
        return None
    os.environ["PATH"] = shim + os.pathsep + os.environ.get("PATH", "")
    os.environ["SOLC_VERSION"] = re.search(r"v(\d+\.\d+\.\d+)", binpath).group(1)
    return binpath
