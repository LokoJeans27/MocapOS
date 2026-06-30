"""
Export the body mesh you see in the MocapOS preview (the gray human overlaid on
the video) to Alembic (.abc) — an exact, animated vertex cache of the mesh.

For each result it writes, into the same results folder, TWO files:

    <video>_mesh_incam.abc    exact mesh per frame, CAMERA space (matches the plate / incam preview)
    <video>_mesh_global.abc   exact mesh per frame, WORLD space  (character in a clean scene)

"incam"  = same space as inputs/<video>/incam.mp4  -> sits exactly on top of the original footage (VFX / Nuke).
"global" = same space as global.mp4                -> world-space, character standing in a clean scene.

When the result includes hands (Full Body + Hands), the mesh is the articulated
SMPL-X body (with fingers); otherwise it is the SMPL body.

This module runs inside the gvhmr conda env: it rebuilds the exact vertices (via
SmplLite / SmplxLite, the same body models used for the preview), dumps them to a
temporary .npz, and then calls Blender headless (tools/export/export_mesh_blender.py)
to write the Alembic.

Usage (standalone):
    python tools/export/export_mesh.py --results_dir outputs/results/MY_VIDEO
    python tools/export/export_mesh.py --results_dir outputs/results/MY_VIDEO --blender "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"
"""

import sys
import os
import glob
import shutil
import argparse
import subprocess
from pathlib import Path

import numpy as np
import torch

GVHMR_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GVHMR_ROOT))

# SMPL 24-joint skeleton (kintree comes from the model itself; names are for readability)
SMPL_24_NAMES = [
    "Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee",
    "Spine2", "L_Ankle", "R_Ankle", "Spine3", "L_Foot", "R_Foot",
    "Neck", "L_Collar", "R_Collar", "Head", "L_Shoulder", "R_Shoulder",
    "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist", "L_Hand", "R_Hand",
]

# The two spaces we export, mapped to the keys stored in hmr4d_results.pt
SPACES = {
    "incam": "smpl_params_incam",
    "global": "smpl_params_global",
}

# SMPL-X 55-joint skeleton (used in hands mode so fingers articulate)
SMPLX_55_NAMES = [
    "Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee",
    "Spine2", "L_Ankle", "R_Ankle", "Spine3", "L_Foot", "R_Foot",
    "Neck", "L_Collar", "R_Collar", "Head", "L_Shoulder", "R_Shoulder",
    "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist", "Jaw", "L_Eye", "R_Eye",
    "L_Index1", "L_Index2", "L_Index3", "L_Middle1", "L_Middle2", "L_Middle3",
    "L_Pinky1", "L_Pinky2", "L_Pinky3", "L_Ring1", "L_Ring2", "L_Ring3",
    "L_Thumb1", "L_Thumb2", "L_Thumb3",
    "R_Index1", "R_Index2", "R_Index3", "R_Middle1", "R_Middle2", "R_Middle3",
    "R_Pinky1", "R_Pinky2", "R_Pinky3", "R_Ring1", "R_Ring2", "R_Ring3",
    "R_Thumb1", "R_Thumb2", "R_Thumb3",
]

# FK chains / indices for the HaMeR wrist fix (must match tools/pipeline/pipeline_fullbody.py)
LEFT_ARM_CHAIN = [2, 5, 8, 12, 15, 17]
RIGHT_ARM_CHAIN = [2, 5, 8, 13, 16, 18]
LEFT_WRIST_IDX = 19   # index into the 21 body-pose joints
RIGHT_WRIST_IDX = 20


def find_blender(explicit=None):
    """Locate blender.exe. Same strategy as the GUI's _detect_blender()."""
    if explicit and Path(explicit).exists():
        return explicit
    found = shutil.which("blender")
    if found:
        return found
    patterns = [
        r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
        r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
        str(Path.home() / "Blender*/blender.exe"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]
    return ""


def _as_tensor(x, shape_last):
    """Coerce a param entry to a float tensor of shape (L, shape_last)."""
    if isinstance(x, np.ndarray):
        x = torch.from_numpy(x)
    x = x.float()
    return x.reshape(-1, shape_last)


def _extract_params(params):
    """Return (L, global_orient(L,3), body_pose(L,63), transl(L,3), betas(L,10))."""
    go = _as_tensor(params["global_orient"], 3)
    bp = _as_tensor(params["body_pose"], 63)
    L = go.shape[0]

    transl = params.get("transl", None)
    if transl is None:
        tr = torch.zeros(L, 3)
    else:
        tr = _as_tensor(transl, 3)

    betas = params.get("betas", None)
    if betas is None:
        be = torch.zeros(L, 10)
    else:
        be = _as_tensor(betas, 10)
        if be.shape[0] == 1:           # single shape -> repeat per frame
            be = be.expand(L, -1).contiguous()
        elif be.shape[0] != L:
            be = be[:1].expand(L, -1).contiguous()
    return L, go, bp, tr, be


def _build_npz_for_space(model, params, npz_path, fps, chunk=200):
    """Compute the exact per-frame SMPL mesh for one space and save to npz_path."""
    L, go, bp, tr, betas = _extract_params(params)

    # GVHMR/SMPLX body_pose covers 21 joints (63). The native SMPL model expects
    # 23 body joints (69): pad the 2 hand joints (L_Hand, R_Hand) with zeros.
    def pad_body_pose(bp_):
        return torch.cat([bp_, torch.zeros(bp_.shape[0], 6)], dim=-1)

    # Exact deformed vertices per frame (this is literally the previewed mesh)
    faces = np.asarray(model.faces).astype(np.int64)
    V = model.v_template.shape[0]
    verts = np.empty((L, V, 3), dtype=np.float32)
    with torch.no_grad():
        for s in range(0, L, chunk):
            e = min(s + chunk, L)
            v = model(
                body_pose=pad_body_pose(bp[s:e]),
                betas=betas[s:e],
                global_orient=go[s:e],
                transl=tr[s:e],
            )
            verts[s:e] = v.cpu().numpy()

    np.savez_compressed(
        npz_path,
        faces=faces,
        verts=verts,
        fps=np.array([fps], dtype=np.float32),
    )
    return L


def _smplx_verts(model, full_pose_aa, betas, transl):
    """SMPL-X LBS with a full 55-joint axis-angle pose (lets us inject finger
    poses). Matches SmplxLite.forward exactly (validated to 0 diff)."""
    from pytorch3d.transforms import axis_angle_to_matrix
    from hmr4d.utils.body_model.smplx_lite import batch_rigid_transform_v2
    from einops import einsum as E
    rot = axis_angle_to_matrix(full_pose_aa)                 # (L,55,3,3)
    J = model.get_skeleton(betas)                            # (L,55,3)
    A = batch_rigid_transform_v2(rot, J, model.parents)[1]
    eye = rot.new_tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    pf = (rot[:, 1:] - eye).reshape(rot.shape[0], -1)
    v_posed = (model.v_template
               + E(betas, model.shapedirs, "l k, v c k -> l v c")
               + E(pf, model.posedirs, "l k, k v c -> l v c"))
    Tm = E(model.lbs_weights, A, "v j, l j c d -> l v c d")
    verts = E(Tm[..., :3, :3], v_posed, "l v c d, l v d -> l v c") + Tm[..., :3, 3]
    return verts + transl[:, None, :]


def _clamp_wrist_aa(aa, fallback, max_angle=0.5, comp_max=0.4):
    if torch.norm(aa) > max_angle or torch.any(torch.abs(aa) > comp_max):
        return fallback
    return aa


def _compute_wrist_aa(incam_params, hr):
    """Replicates pipeline_fullbody.compute_wrist_rotations so the exported wrists
    match the hand-mode preview exactly."""
    from pytorch3d.transforms import axis_angle_to_matrix, matrix_to_axis_angle
    lwo = hr.get("left_wrist_orient")
    rwo = hr.get("right_wrist_orient")
    go = incam_params["global_orient"].cpu().reshape(-1, 3).float()
    bp = incam_params["body_pose"].cpu().reshape(-1, 21, 3).float()
    L = len(go)
    if lwo is None or rwo is None:
        return bp[:, LEFT_WRIST_IDX].clone(), bp[:, RIGHT_WRIST_IDX].clone()
    lwo = lwo.cpu().float(); rwo = rwo.cpu().float()
    R_root = axis_angle_to_matrix(go)
    R_body = axis_angle_to_matrix(bp.reshape(-1, 3)).reshape(L, 21, 3, 3)
    law = torch.zeros(L, 3); raw = torch.zeros(L, 3)
    for i in range(L):
        if lwo[i].abs().sum() > 0.1:
            G = R_root[i]
            for k in LEFT_ARM_CHAIN:
                G = G @ R_body[i, k]
            aa = matrix_to_axis_angle((G.T @ lwo[i]).unsqueeze(0))[0]
            law[i] = _clamp_wrist_aa(aa, bp[i, LEFT_WRIST_IDX])
        else:
            law[i] = bp[i, LEFT_WRIST_IDX]
        if rwo[i].abs().sum() > 0.1:
            G = R_root[i]
            for k in RIGHT_ARM_CHAIN:
                G = G @ R_body[i, k]
            aa = matrix_to_axis_angle((G.T @ rwo[i]).unsqueeze(0))[0]
            raw[i] = _clamp_wrist_aa(aa, bp[i, RIGHT_WRIST_IDX])
        else:
            raw[i] = bp[i, RIGHT_WRIST_IDX]
    return law, raw


def _build_npz_smplx(model, params, hr, law, raw, npz_path, fps, chunk=100):
    """Hands mode: build the exact articulated SMPL-X mesh (with fingers) per frame."""
    L, go, bp63, tr, betas = _extract_params(params)
    lhp = _as_tensor(hr["left_hand_pose"], 45).reshape(-1, 15, 3)
    rhp = _as_tensor(hr["right_hand_pose"], 45).reshape(-1, 15, 3)

    # Full 55-joint local axis-angle pose (body + HaMeR fingers + wrist fix)
    pose = torch.zeros(L, 55, 3)
    pose[:, 0] = go
    pose[:, 1:22] = bp63.reshape(L, 21, 3)
    pose[:, 1 + LEFT_WRIST_IDX] = law          # HaMeR wrist fix (same as preview)
    pose[:, 1 + RIGHT_WRIST_IDX] = raw
    # joints 22-24 (jaw, eyes) stay zero
    pose[:, 25:40] = lhp
    pose[:, 40:55] = rhp

    faces = np.asarray(model.faces).astype(np.int64)
    V = model.v_template.shape[0]
    verts = np.empty((L, V, 3), dtype=np.float32)
    with torch.no_grad():
        for s in range(0, L, chunk):
            e = min(s + chunk, L)
            verts[s:e] = _smplx_verts(model, pose[s:e], betas[s:e], tr[s:e]).cpu().numpy()

    np.savez_compressed(
        npz_path,
        faces=faces,
        verts=verts,
        fps=np.array([fps], dtype=np.float32),
    )
    return L


def run_export(results_dir, blender=None, fps=30, keep_npz=False):
    """
    Main entry point. Reads hmr4d_results.pt from results_dir and writes the
    Alembic (.abc) mesh cache for both incam and global spaces.

    Returns True if at least one Blender export succeeded.
    """
    results_dir = Path(results_dir)
    pt_path = results_dir / "hmr4d_results.pt"
    if not pt_path.exists():
        print(f"[Mesh Export] hmr4d_results.pt not found in {results_dir}, skipping.")
        return False

    pred = torch.load(str(pt_path), map_location="cpu", weights_only=False)

    # Hands mode: if HaMeR results exist, export an articulated SMPL-X mesh
    # (10475 verts, 55-bone rig with fingers). Otherwise the body SMPL mesh.
    hand_path = results_dir / "hand_results.pt"
    hands = hand_path.exists()
    law = raw = hr = None
    try:
        if hands:
            from hmr4d.utils.body_model.smplx_lite import SmplxLite
            model = SmplxLite(model_path=str(GVHMR_ROOT / "inputs/checkpoints/body_models/smplx")).eval()
            hr = torch.load(str(hand_path), map_location="cpu", weights_only=False)
            law, raw = _compute_wrist_aa(pred["smpl_params_incam"], hr)
            print("[Mesh Export] Hands detected -> exporting articulated SMPL-X mesh (fingers).")
        else:
            from hmr4d.utils.body_model.smpl_lite import SmplLite
            model = SmplLite(model_path=str(GVHMR_ROOT / "inputs/checkpoints/body_models/smpl")).eval()
    except Exception as e:
        print(f"[Mesh Export] Could not load body model ({e}).")
        print("[Mesh Export] Need inputs/checkpoints/body_models/{smpl/SMPL_NEUTRAL.pkl | smplx/SMPLX_NEUTRAL.npz}.")
        return False

    blender_exe = find_blender(blender)
    stem = results_dir.name
    any_ok = False

    for space, key in SPACES.items():
        if key not in pred:
            print(f"[Mesh Export] '{key}' not in results, skipping {space}.")
            continue

        npz_path = results_dir / f"_meshcache_{space}.npz"
        print(f"[Mesh Export] Building {space} mesh cache...")
        if hands:
            L = _build_npz_smplx(model, pred[key], hr, law, raw, npz_path, fps)
        else:
            L = _build_npz_for_space(model, pred[key], npz_path, fps)

        abc_path = results_dir / f"{stem}_mesh_{space}.abc"

        if not blender_exe:
            print("[Mesh Export] Blender not found. Mesh cache saved (.npz) but Alembic not written.")
            print("[Mesh Export] Install Blender or pass --blender, then re-run this script.")
            continue

        blender_script = GVHMR_ROOT / "tools" / "export" / "export_mesh_blender.py"
        cmd = [
            blender_exe, "--background", "--python", str(blender_script), "--",
            "--npz", str(npz_path),
            "--abc", str(abc_path),
        ]
        print(f"[Mesh Export] Blender -> {abc_path.name}  ({L} frames)")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[Mesh Export] Blender failed for {space} (exit {res.returncode}).")
                print(res.stdout[-2000:])
                print(res.stderr[-2000:])
            else:
                any_ok = True
                print(f"[Mesh Export] OK: {abc_path.name}")
        except Exception as e:
            print(f"[Mesh Export] Error running Blender for {space}: {e}")

        if not keep_npz:
            try:
                npz_path.unlink()
            except OSError:
                pass

    if any_ok:
        print(f"[Mesh Export] Done. Files written to: {results_dir}")
    return any_ok


def main():
    parser = argparse.ArgumentParser(description="Export the previewed body mesh to Alembic (.abc)")
    parser.add_argument("--results_dir", required=True,
                        help="Folder containing hmr4d_results.pt (e.g. outputs/results/MY_VIDEO)")
    parser.add_argument("--blender", default=None, help="Path to blender.exe (auto-detected if omitted)")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--keep_npz", action="store_true", help="Keep the intermediate mesh cache .npz")
    args = parser.parse_args()
    os.chdir(str(GVHMR_ROOT))
    ok = run_export(args.results_dir, blender=args.blender, fps=args.fps, keep_npz=args.keep_npz)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
