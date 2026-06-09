"""
Convert GVHMR/HaMeR inference output (.pt) to a Blender-friendly .npz file.

Why: Blender's bundled Python doesn't have torch, but does have numpy.
This step reads the SMPL-X parameters and emits axis-angle rotations + root
translation as a plain .npz.

The output .npz is consumed by retarget_blender.py to apply rotations directly
to a Mixamo armature (X Bot.fbx) — no BVH intermediate needed, so bone names
and measurements are Mixamo from the start.

Usage:
    python tools/retarget/prepare_motion.py \\
        --results_dir outputs/results/REF \\
        --out outputs/results/REF/motion.npz
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch


SMPLX_JOINT_NAMES = [
    "Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee",
    "Spine2", "L_Ankle", "R_Ankle", "Spine3", "L_Foot", "R_Foot",
    "Neck", "L_Collar", "R_Collar", "Head", "L_Shoulder", "R_Shoulder",
    "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist",
    "Jaw", "L_Eye", "R_Eye",
    "L_Index1", "L_Index2", "L_Index3",
    "L_Middle1", "L_Middle2", "L_Middle3",
    "L_Pinky1", "L_Pinky2", "L_Pinky3",
    "L_Ring1", "L_Ring2", "L_Ring3",
    "L_Thumb1", "L_Thumb2", "L_Thumb3",
    "R_Index1", "R_Index2", "R_Index3",
    "R_Middle1", "R_Middle2", "R_Middle3",
    "R_Pinky1", "R_Pinky2", "R_Pinky3",
    "R_Ring1", "R_Ring2", "R_Ring3",
    "R_Thumb1", "R_Thumb2", "R_Thumb3",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--body_only", action="store_true")
    args = ap.parse_args()

    rd = Path(args.results_dir)
    body_path = rd / "hmr4d_results.pt"
    if not body_path.exists():
        print(f"ERROR: missing {body_path}")
        sys.exit(1)

    print(f"Loading {body_path}")
    body = torch.load(str(body_path), map_location="cpu", weights_only=False)
    params = body["smpl_params_global"]

    go = params["global_orient"].numpy().reshape(-1, 1, 3)
    bp = params["body_pose"].numpy().reshape(-1, 21, 3)
    tr = params.get("transl", torch.zeros(len(go), 3))
    if isinstance(tr, torch.Tensor):
        tr = tr.numpy()
    tr = tr.reshape(-1, 3)
    L = len(go)

    hand_path = rd / "hand_results.pt"
    has_hands = hand_path.exists() and not args.body_only

    if has_hands:
        print(f"Loading {hand_path}")
        hr = torch.load(str(hand_path), map_location="cpu", weights_only=False)
        lh = hr["left_hand_pose"].numpy().reshape(L, 15, 3)
        rh = hr["right_hand_pose"].numpy().reshape(L, 15, 3)
        n_joints = 55
        rot = np.zeros((L, 55, 3), dtype=np.float32)
        rot[:, 0:1] = go
        rot[:, 1:22] = bp
        rot[:, 25:40] = lh
        rot[:, 40:55] = rh
    else:
        n_joints = 22
        rot = np.zeros((L, 22, 3), dtype=np.float32)
        rot[:, 0:1] = go
        rot[:, 1:22] = bp

    names = SMPLX_JOINT_NAMES[:n_joints]

    # ── Ground-snap translation (mirror demo.py move_to_start_point_face_z) ──
    # Raw SMPL-X transl is pelvis world position; without normalization the
    # character "floats" because proportions differ from the X Bot rest pose.
    # We compute the SMPL-X mesh vertices, find the minimum Y across all frames,
    # and shift transl so the lowest point sits at Y=0. Also center XZ at frame 0.
    try:
        from hmr4d.utils.smplx_utils import make_smplx
        m = make_smplx("supermotion", use_pca=False, flat_hand_mean=True)
        with torch.no_grad():
            smplx_out = m(
                betas=params["betas"][:1].float() if isinstance(params["betas"], torch.Tensor) else torch.zeros(1, 10),
                global_orient=torch.from_numpy(go.reshape(-1, 3)).float(),
                body_pose=torch.from_numpy(bp.reshape(-1, 63)).float(),
                transl=torch.from_numpy(tr).float(),
            )
        verts = smplx_out.vertices.cpu().numpy()  # (L, V, 3)
        # frame 0 pelvis in world ≈ verts[0] mean? use J_regressor for accuracy
        # but a quick approximation: use transl[0] for XZ, verts.min(Y) for ground.
        min_y = verts[:, :, 1].min()
        offset_x = float(tr[0, 0])
        offset_z = float(tr[0, 2])
        offset_y = float(min_y)
        tr = tr.copy()
        tr[:, 0] -= offset_x
        tr[:, 1] -= offset_y
        tr[:, 2] -= offset_z
        print(f"Ground-snap: subtracted offset=({offset_x:.3f}, {offset_y:.3f}, {offset_z:.3f}) m")
    except Exception as e:
        print(f"Ground-snap skipped: {e}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_path,
        rot_aa=rot.astype(np.float32),
        transl=tr.astype(np.float32),
        joint_names=np.array(names),
        fps=np.int32(args.fps),
        n_frames=np.int32(L),
        n_joints=np.int32(n_joints),
    )
    print(f"Saved {out_path}: {L} frames, {n_joints} joints, fps={args.fps}")


if __name__ == "__main__":
    main()
