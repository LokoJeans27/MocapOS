"""MocapOS self-test — proves an install can actually run inference on THIS GPU.

Levels (each prints PASS/FAIL and the test keeps going to give a full report):
  1. Imports     : torch, numpy(<2), pytorch3d._C, detectron2, hmr4d, smplx
  2. GPU kernels : a real CUDA matmul + a pytorch3d CUDA op. This is what catches
                   "no kernel image is available for execution on the device",
                   i.e. a torch/CUDA build that lacks this GPU's architecture
                   (the classic GTX 1000 / sm_61 on a cu128 wheel failure).
  3. Models      : every tracking model in models_manifest.json is present and the
                   right size (use --verify-hash for full SHA256, slow on ~12 GB).
  4. Inference   : with --full and SMPL/SMPL-X present, runs the real body pipeline
                   on docs/example_video/tennis.mp4 and checks hmr4d_results.pt.

Exit code 0 only if every attempted level passed. Usage:
    python tools/dev/selftest.py            # levels 1-3 (fast, no body models needed)
    python tools/dev/selftest.py --full     # also run real inference (needs SMPL/SMPL-X)
    python tools/dev/selftest.py --verify-hash
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[2]
results = []


def record(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f" - {detail}" if detail else ""), flush=True)
    results.append((name, ok))
    return ok


def section(title):
    print(f"\n=== {title} ===", flush=True)


def test_imports():
    section("1. Imports")
    try:
        import torch
        record("torch", True, torch.__version__)
    except Exception as e:
        return record("torch", False, repr(e))
    try:
        import numpy
        ok = numpy.__version__.startswith("1.")
        record("numpy<2", ok, numpy.__version__)
    except Exception as e:
        record("numpy", False, repr(e))
    for mod, label in [("pytorch3d", "pytorch3d"), ("detectron2", "detectron2"),
                       ("hmr4d", "hmr4d"), ("smplx", "smplx")]:
        try:
            __import__(mod)
            record(label, True)
        except Exception as e:
            record(label, False, repr(e))
    # pytorch3d native extension specifically (links torch DLLs; import torch first)
    try:
        import torch  # noqa: F811
        from pytorch3d import _C  # noqa: F401
        record("pytorch3d._C", True)
    except Exception as e:
        record("pytorch3d._C", False, repr(e))


def test_gpu_kernels():
    section("2. GPU kernels (catches arch/kernel-image mismatch)")
    import torch
    if not torch.cuda.is_available():
        return record("cuda.is_available", False,
                      "No CUDA device visible — check NVIDIA driver")
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    record("cuda device", True, f"{name} sm_{cap[0]}{cap[1]}, torch cuda={torch.version.cuda}")
    # Real kernel launch — fails loudly if this arch is not in the wheel.
    try:
        x = torch.randn(512, 512, device="cuda")
        y = (x @ x).relu().sum().item()
        torch.cuda.synchronize()
        record("torch CUDA matmul", True, f"checksum={y:.1f}")
    except Exception as e:
        record("torch CUDA matmul", False, repr(e))
    # pytorch3d CUDA op (knn uses its compiled CUDA kernels).
    try:
        from pytorch3d.ops import knn_points
        a = torch.rand(1, 64, 3, device="cuda")
        b = torch.rand(1, 64, 3, device="cuda")
        knn_points(a, b, K=4)
        torch.cuda.synchronize()
        record("pytorch3d CUDA knn", True)
    except Exception as e:
        record("pytorch3d CUDA knn", False, repr(e))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_models(verify_hash):
    section("3. Tracking models")
    mf = PROJ_ROOT / "models_manifest.json"
    if not mf.exists():
        return record("models_manifest.json", False, "not found")
    data = json.loads(mf.read_text(encoding="utf-8"))
    all_ok = True
    for m in data["models"]:
        p = PROJ_ROOT / m["path"]
        label = m["path"].split("/")[-1]
        if not p.exists():
            all_ok = record(label, False, "missing") and all_ok
            continue
        if p.stat().st_size != m["size"]:
            all_ok = record(label, False,
                            f"size {p.stat().st_size} != {m['size']}") and all_ok
            continue
        if verify_hash:
            if _sha256(p) != m["sha256"]:
                all_ok = record(label, False, "sha256 mismatch") and all_ok
                continue
        record(label, True, "size+hash" if verify_hash else "size")
    return all_ok


def _body_models_present():
    smplx = PROJ_ROOT / "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz"
    smpl = PROJ_ROOT / "inputs/checkpoints/body_models/smpl/SMPL_NEUTRAL.pkl"
    return smplx.exists() and smpl.exists()


def test_inference():
    section("4. Real inference (body pipeline)")
    if not _body_models_present():
        record("body models present", False,
               "SMPL/SMPL-X not found — download via the GUI importer to run real inference")
        return
    video = PROJ_ROOT / "docs/example_video/tennis.mp4"
    if not video.exists():
        return record("example video", False, str(video))
    out_root = PROJ_ROOT / "outputs" / "selftest"
    cmd = [sys.executable, "-u", "tools/pipeline/pipeline.py",
           "--video", str(video), "-s", "--output_root", str(out_root)]
    print("  running:", " ".join(cmd[2:]), flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(PROJ_ROOT))
    dt = time.time() - t0
    if proc.returncode != 0:
        return record("pipeline.py", False, f"exit {proc.returncode}")
    result = out_root / video.stem / "hmr4d_results.pt"
    record("hmr4d_results.pt", result.exists(), f"{dt:.0f}s -> {result}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="also run real inference")
    ap.add_argument("--verify-hash", action="store_true", help="full SHA256 of models")
    args = ap.parse_args()

    print("MocapOS self-test")
    print(f"app root : {PROJ_ROOT}")
    print(f"python   : {sys.executable}")

    test_imports()
    test_gpu_kernels()
    test_models(args.verify_hash)
    if args.full:
        test_inference()

    section("Summary")
    failed = [n for n, ok in results if not ok]
    if failed:
        print(f"  {len(failed)} check(s) FAILED: " + ", ".join(failed))
        print("\n  RESULT: NOT READY")
        sys.exit(1)
    print(f"  All {len(results)} checks passed.")
    print("\n  RESULT: READY")
    sys.exit(0)


if __name__ == "__main__":
    main()
