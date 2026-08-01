import argparse, json, shutil
from pathlib import Path

PILOTS = ["re", "arith", "ac", "unchk"]

OVERRIDES = {
    "uc_keepether":   ("unchecked_patched", "keepMyEther.sol"),
    "uc_depproxy":    ("unchecked_patched", "depositproxy.sol"),
    "uc_vaultproxy1": ("unchecked_patched", "vaultproxy1.sol"),
    "uc_vaultproxy2": ("unchecked_patched", "vaultproxy2.sol"),
    "uc_etherget":    ("unchecked_patched", "etherget.sol"),
}


def build_map(repo):
    m = {}
    for p in PILOTS:
        for r in json.loads((repo / f"manifest_pilot_{p}.json").read_text()):
            c = Path(r["contract"])
            m[r["stem"]] = (f"{c.parent.name}_patched", c.name)
    m.update(OVERRIDES)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--sbh", required=True)
    ap.add_argument("--repo", default=str(Path(__file__).parent))
    a = ap.parse_args()

    repo = Path(a.repo)
    src_dir = repo / "patches" / "ablate" / a.config
    dataset = Path(a.sbh) / "contracts" / "dataset"
    mapping = build_map(repo)

    staged = missing = 0
    for stem, (folder, fname) in mapping.items():
        src = src_dir / f"{stem}.sol"
        if not src.is_file():
            print(f"MISSING {stem}: {src}")
            missing += 1
            continue
        dst_dir = dataset / folder
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst_dir / fname)
        staged += 1
        print(f"STAGED {stem} -> {folder}/{fname}")
    print(f"\n[{a.config}] staged={staged} missing={missing}")


if __name__ == "__main__":
    main()
