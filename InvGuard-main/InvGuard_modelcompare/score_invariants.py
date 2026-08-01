import json, glob, sys
from pathlib import Path

tags = sys.argv[1:]
if not tags:
    print("usage: score_invariants.py <tag> [<tag> ...]")
    sys.exit(1)

ver = vio = unk = uns = rej = 0
for tag in tags:
    for sj in glob.glob(f"results/{tag}/*/flow1_outputs/verified_invariants.*.summary.json"):
        d = json.load(open(sj))
        ver += d.get("verified_count", 0)
        vio += d.get("violated_count", 0)
        unk += d.get("unknown_count", 0)
        uns += d.get("unsound_count", 0)
        rej += d.get("rejected_count", 0)

raw = ver + vio + unk + uns + rej
rejtot = vio + uns + rej
if raw == 0:
    print("no invariants found for tags:", tags)
else:
    print(f"raw={raw} verified={ver} rejected={rejtot} (falsified={vio} unsupported={rej}) "
          f"unknown={unk} halluc={100*rejtot/raw:.1f}%")
