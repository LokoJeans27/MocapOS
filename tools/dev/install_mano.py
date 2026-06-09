"""Install MANO hand models from the user's own mano_v1_2.zip.

MANO is licensed (Max Planck). We never redistribute it. The user downloads
mano_v1_2.zip themselves from https://mano.is.tue.mpg.de/ (accepting the license),
and this script just extracts MANO_LEFT.pkl + MANO_RIGHT.pkl from that zip and
places them where HaMeR expects them. Nothing is downloaded from the internet here.

Usage:
    env\\python.exe tools\\dev\\install_mano.py [path\\to\\mano_v1_2.zip]

If no path is given, it auto-searches Downloads / Desktop / the project folder
for a mano*.zip. Exit code 0 on success, 1 if it could not install.
"""

import glob
import os
import sys
import zipfile
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[2]
DEST = PROJ_ROOT / "hamer_lib" / "_DATA" / "data" / "mano"
WANTED = ["MANO_LEFT.pkl", "MANO_RIGHT.pkl"]


def find_zip() -> Path | None:
    # 1) explicit path argument
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser()
        if p.is_file():
            return p
        print(f"[WARN] Not a file: {p}")
    # 2) auto-search common locations
    home = Path.home()
    search_dirs = [home / "Downloads", home / "Desktop", PROJ_ROOT, Path.cwd()]
    hits: list[str] = []
    for d in search_dirs:
        hits += glob.glob(str(d / "mano_v1_2*.zip"))
        hits += glob.glob(str(d / "*[Mm][Aa][Nn][Oo]*.zip"))
    # newest first
    hits = sorted(set(hits), key=lambda f: os.path.getmtime(f), reverse=True)
    return Path(hits[0]) if hits else None


def main() -> int:
    zp = find_zip()
    if zp is None:
        print("[ERROR] Could not find mano_v1_2.zip.")
        print("  Download 'Models & Code' from https://mano.is.tue.mpg.de/ , then run:")
        print("    env\\python.exe tools\\dev\\install_mano.py <path-to-mano_v1_2.zip>")
        return 1

    print(f"[MANO] Installing from: {zp}")
    try:
        with zipfile.ZipFile(zp) as z:
            members = {os.path.basename(n): n for n in z.namelist()}
            DEST.mkdir(parents=True, exist_ok=True)
            done = {}
            for want in WANTED:
                src_name = members.get(want)
                if not src_name:
                    continue
                data = z.read(src_name)
                (DEST / want).write_bytes(data)
                done[want] = len(data)
                print(f"  extracted {want} ({len(data):,} bytes) -> {DEST / want}")
    except zipfile.BadZipFile:
        print(f"[ERROR] Not a valid zip: {zp}")
        return 1

    missing = [w for w in WANTED if w not in done]
    if missing:
        print(f"[ERROR] These files were not inside the zip: {missing}")
        print("  Make sure you downloaded 'Models & Code' (mano_v1_2.zip), not the SMPL+H variants.")
        return 1

    print("[OK] MANO installed. Re-run the inference to get hands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
