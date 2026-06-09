"""Build models_manifest.json from the known-good tracking checkpoints on this PC.

Run on the BUILD machine (where models are present and verified working). The
manifest records, for each PUBLIC tracking model, its relative install path, the
HuggingFace download URL, the exact byte size and the SHA256. setup.bat uses it
to download + verify on the user's machine, so a partial/corrupt download is
caught by hash instead of silently passing an "if exist" check.

License note: SMPL / SMPL-X body models are NOT included here. They are licensed
by Max Planck and must be downloaded by each user; we neither redistribute them
nor pin their hashes.
"""

import hashlib
import json
import sys
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[2]

# (relative install path, HuggingFace URL). Paths are relative to the app root.
MODELS = [
    ("inputs/checkpoints/gvhmr/gvhmr_siga24_release.ckpt",
     "https://huggingface.co/camenduru/GVHMR/resolve/main/gvhmr/gvhmr_siga24_release.ckpt"),
    ("inputs/checkpoints/hmr2/epoch=10-step=25000.ckpt",
     "https://huggingface.co/camenduru/GVHMR/resolve/main/hmr2/epoch%3D10-step%3D25000.ckpt"),
    ("inputs/checkpoints/vitpose/vitpose-h-multi-coco.pth",
     "https://huggingface.co/camenduru/GVHMR/resolve/main/vitpose/vitpose-h-multi-coco.pth"),
    ("inputs/checkpoints/dpvo/dpvo.pth",
     "https://huggingface.co/camenduru/GVHMR/resolve/main/dpvo/dpvo.pth"),
    ("inputs/checkpoints/yolo/yolov8x.pt",
     "https://huggingface.co/camenduru/GVHMR/resolve/main/yolo/yolov8x.pt"),
    ("hamer_lib/_DATA/hamer_ckpts/checkpoints/hamer.ckpt",
     "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/hamer_ckpts/checkpoints/hamer.ckpt"),
    ("hamer_lib/_DATA/vitpose_ckpts/vitpose+_huge/wholebody.pth",
     "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/vitpose_ckpts/vitpose%2B_huge/wholebody.pth"),
    ("hamer_lib/_DATA/hamer_ckpts/model_config.yaml",
     "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/hamer_ckpts/model_config.yaml"),
    ("hamer_lib/_DATA/hamer_ckpts/dataset_config.yaml",
     "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/hamer_ckpts/dataset_config.yaml"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    entries = []
    missing = []
    for rel, url in MODELS:
        p = PROJ_ROOT / rel
        if not p.exists():
            missing.append(rel)
            print(f"[MISSING] {rel}")
            continue
        size = p.stat().st_size
        print(f"[HASH] {rel} ({size/1e6:.1f} MB) ...", flush=True)
        digest = sha256(p)
        entries.append({"path": rel, "url": url, "size": size, "sha256": digest})
        print(f"        {digest}")

    if missing:
        print(f"\nERROR: {len(missing)} model(s) missing on this build machine; "
              f"cannot create a complete manifest.", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(1)

    out = PROJ_ROOT / "models_manifest.json"
    out.write_text(json.dumps({"models": entries}, indent=2), encoding="utf-8")
    print(f"\nWrote {out} with {len(entries)} entries.")


if __name__ == "__main__":
    main()
