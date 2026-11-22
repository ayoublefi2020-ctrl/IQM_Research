import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research_data/distance_3"
GROUPS = "raw_hardware processed_measurements detectors decoding calibration compiled_circuits twirling statistics figures metadata".split()

def category(path):
    name = path.name.lower()
    if path.suffix in (".png", ".pdf", ".svg"):
        return "figures"
    if "counts" in name or "-raw." in name:
        return "raw_hardware"
    if "detector" in name or "syndrome" in name:
        return "detectors"
    if "calibration" in name:
        return "calibration"
    if "blocks" in name:
        return "processed_measurements"
    if "decoder" in name:
        return "decoding"
    if "audit" in name or "layout" in name or path.suffix == ".stim":
        return "compiled_circuits"
    if name == "comparison.json" and "twirl" in str(path):
        return "twirling"
    if "summary" in name or "score" in name or "fit" in name or "errors" in name:
        return "statistics"
    return "metadata"

def snapshot():
    for group in GROUPS:
        (ARCHIVE / group).mkdir(parents=True, exist_ok=True)
    entries = {}
    for source in sorted((ROOT / "results").rglob("*")):
        if not source.is_file() or source.name.startswith("."):
            continue
        relative = source.relative_to(ROOT)
        if relative.parts[1] == "distance5_rate":
            continue
        data = source.read_bytes()
        target = ARCHIVE / category(source) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        digest = hashlib.sha256(data).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Archive/source mismatch: {relative}")
        entries[relative.as_posix()] = dict(file=target.relative_to(ARCHIVE).as_posix(), sha256=digest, bytes=len(data))
    (ARCHIVE / "manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"Verified {len(entries)} source and archive checksums")
    return entries

if __name__ == "__main__":
    snapshot()
