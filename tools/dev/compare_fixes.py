"""Iterate axis fixes: re-export FBX, render frame 1, save side-by-side vs global_1.png."""
import subprocess
import sys
import os
from pathlib import Path

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
PROJ = Path(r"C:\Users\User\Documents\MocapOS")
NPZ = PROJ / "outputs" / "demo" / "REF" / "motion.npz"
CHAR = r"C:\Users\User\Downloads\X Bot.fbx"
TEST_BLEND = r"C:\Users\User\Desktop\test.blend"
OUT_DIR = Path(r"C:\Users\User\Desktop\axis_compare")
OUT_DIR.mkdir(exist_ok=True)
GLOBAL_REF = Path(r"C:\Users\User\Documents\MocapOS\outputs\results\REF\global_1.png")

retarget_script = str(PROJ / "tools" / "retarget" / "retarget_blender.py")
render_script = str(PROJ / "tools" / "retarget" / "render_test.py")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def try_fix(fix_name):
    fbx = str(OUT_DIR / f"REF_{fix_name}.fbx")
    rc, _, _ = run([
        BLENDER, "--background", "--python", retarget_script, "--",
        "--npz", str(NPZ), "--character", CHAR,
        "--output", fbx, "--axis_fix", fix_name,
    ])
    if rc != 0:
        print(f"  FAIL retarget: {fix_name}")
        return None
    rndr = str(OUT_DIR / f"render_{fix_name}")
    Path(rndr).mkdir(exist_ok=True)
    rc, _, _ = run([
        BLENDER, "--background", TEST_BLEND, "--python", render_script, "--",
        "--fbx", fbx, "--frames", "1", "--out_dir", rndr,
    ])
    if rc != 0:
        print(f"  FAIL render: {fix_name}")
        return None
    return Path(rndr) / "render_0001.png"


fixes = ["none", "conj_x90", "conj_xneg90", "pre_x90", "pre_xneg90",
         "conj_x90_z180", "conj_xneg90_z180", "conj_x90_y180"]

results = {}
for f in fixes:
    print(f"== Trying: {f} ==")
    p = try_fix(f)
    if p and p.exists():
        results[f] = str(p)
        print(f"  OK -> {p}")

print("\nResults:")
for f, p in results.items():
    print(f"  {f}: {p}")
print(f"\nReference: {GLOBAL_REF}")
