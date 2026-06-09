"""Download + verify the tracking models listed in models_manifest.json.

This replaces the old "curl then if-exist" flow that let a truncated/corrupt
download pass as valid (the "check invalido" bug). Here, every file is checked
by exact byte size, and every freshly downloaded file is verified by SHA256
before being accepted. A bad file is deleted and re-downloaded from scratch
(never `curl -C -` onto a corrupt file), up to a few attempts.

Public HuggingFace models only. SMPL / SMPL-X body models are licensed and are
NOT fetched here — the GUI importer handles those.

Run with the bundled env python:
    env\\python.exe tools\\dev\\fetch_models.py
Exit code 0 if all models are present and valid, 1 otherwise.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[2]
MAX_ATTEMPTS = 3


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def curl(url: str, dest: Path) -> bool:
    """Fresh download (no resume) to dest. Returns True on curl success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    cmd = ["curl.exe", "-L", "--fail", "--retry", "3", "--retry-delay", "5",
           "-o", str(tmp), url]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        if tmp.exists():
            tmp.unlink()
        return False
    os.replace(tmp, dest)
    return True


def need_download(path: Path, size: int) -> bool:
    return not path.exists() or path.stat().st_size != size


def ensure(model: dict) -> bool:
    rel, url, size, want = model["path"], model["url"], model["size"], model["sha256"]
    dest = PROJ_ROOT / rel
    label = rel.split("/")[-1]

    # Already present and correct size -> trust it (full re-hash of ~12 GB every
    # run is wasteful; size catches truncation, and any fresh download below is
    # hash-verified).
    if not need_download(dest, size):
        print(f"  [OK]   {label} (present, {size/1e6:.1f} MB)", flush=True)
        return True

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"  [GET]  {label} ({size/1e6:.1f} MB) attempt {attempt}/{MAX_ATTEMPTS}...",
              flush=True)
        if dest.exists():
            dest.unlink()
        if not curl(url, dest):
            print(f"         download failed (curl). retrying...", flush=True)
            continue
        if dest.stat().st_size != size:
            print(f"         size {dest.stat().st_size} != expected {size}. retrying...",
                  flush=True)
            continue
        print(f"         verifying SHA256...", flush=True)
        if sha256(dest) != want:
            print(f"         SHA256 mismatch -> corrupt. deleting + retrying...",
                  flush=True)
            dest.unlink()
            continue
        print(f"  [OK]   {label} downloaded + verified.", flush=True)
        return True

    print(f"  [FAIL] {label}: could not obtain a valid copy after "
          f"{MAX_ATTEMPTS} attempts.", flush=True)
    return False


def main():
    mf = PROJ_ROOT / "models_manifest.json"
    if not mf.exists():
        print(f"ERROR: {mf} not found.", file=sys.stderr)
        sys.exit(1)
    if not shutil.which("curl.exe") and not shutil.which("curl"):
        print("ERROR: curl not found (needs Windows 10+).", file=sys.stderr)
        sys.exit(1)

    models = json.loads(mf.read_text(encoding="utf-8"))["models"]
    print(f"Fetching {len(models)} tracking models into {PROJ_ROOT}\n")
    ok = True
    for m in models:
        ok = ensure(m) & ok

    print()
    if ok:
        print("All tracking models present and verified.")
        sys.exit(0)
    print("Some models could not be downloaded/verified. Re-run setup or check "
          "your internet connection.")
    sys.exit(1)


if __name__ == "__main__":
    main()
