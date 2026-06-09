"""
Export GVHMR (+HaMeR) motion capture results to BVH (Biovision Hierarchy) format.
BVH files can be imported into Blender, Unity, Unreal, Maya, 3ds Max, etc.
for retargeting motion to any rigged 3D character.

Usage:
    python tools/export/export_bvh.py --results_dir outputs/results/MY_VIDEO
    python tools/export/export_bvh.py --results_dir outputs/results/MY_VIDEO --body_only
    python tools/export/export_bvh.py --results_dir outputs/results/MY_VIDEO --fps 24 --output motion.bvh
"""

import sys
import os
import torch
import numpy as np
import argparse
from pathlib import Path
from scipy.spatial.transform import Rotation

GVHMR_ROOT = Path(__file__).resolve().parents[2]
HAMER_ROOT = GVHMR_ROOT / "hamer_lib"
sys.path.insert(0, str(GVHMR_ROOT))
sys.path.insert(0, str(HAMER_ROOT))

# ── SMPL-X skeleton (55 joints) ──────────────────────────────────────────────

SMPLX_JOINT_NAMES = [
    # Body (0-21)
    'Pelvis', 'L_Hip', 'R_Hip', 'Spine1', 'L_Knee', 'R_Knee',
    'Spine2', 'L_Ankle', 'R_Ankle', 'Spine3', 'L_Foot', 'R_Foot',
    'Neck', 'L_Collar', 'R_Collar', 'Head', 'L_Shoulder', 'R_Shoulder',
    'L_Elbow', 'R_Elbow', 'L_Wrist', 'R_Wrist',
    # Face (22-24)
    'Jaw', 'L_Eye', 'R_Eye',
    # Left Hand (25-39)
    'L_Index1', 'L_Index2', 'L_Index3',
    'L_Middle1', 'L_Middle2', 'L_Middle3',
    'L_Pinky1', 'L_Pinky2', 'L_Pinky3',
    'L_Ring1', 'L_Ring2', 'L_Ring3',
    'L_Thumb1', 'L_Thumb2', 'L_Thumb3',
    # Right Hand (40-54)
    'R_Index1', 'R_Index2', 'R_Index3',
    'R_Middle1', 'R_Middle2', 'R_Middle3',
    'R_Pinky1', 'R_Pinky2', 'R_Pinky3',
    'R_Ring1', 'R_Ring2', 'R_Ring3',
    'R_Thumb1', 'R_Thumb2', 'R_Thumb3',
]

SMPLX_PARENTS = [
    -1,  0,  0,  0,  1,  2,    # 0-5:   Pelvis, hips, spine1, knees
     3,  4,  5,  6,  7,  8,    # 6-11:  spine2, ankles, spine3, feet
     9,  9,  9, 12, 13, 14,    # 12-17: neck, collars, head, shoulders
    16, 17, 18, 19,             # 18-21: elbows, wrists
    15, 15, 15,                 # 22-24: jaw, eyes -> head
    20, 25, 26,                 # 25-27: L_Index  -> L_Wrist
    20, 28, 29,                 # 28-30: L_Middle -> L_Wrist
    20, 31, 32,                 # 31-33: L_Pinky  -> L_Wrist
    20, 34, 35,                 # 34-36: L_Ring   -> L_Wrist
    20, 37, 38,                 # 37-39: L_Thumb  -> L_Wrist
    21, 40, 41,                 # 40-42: R_Index  -> R_Wrist
    21, 43, 44,                 # 43-45: R_Middle -> R_Wrist
    21, 46, 47,                 # 46-48: R_Pinky  -> R_Wrist
    21, 49, 50,                 # 49-51: R_Ring   -> R_Wrist
    21, 52, 53,                 # 52-54: R_Thumb  -> R_Wrist
]


def build_children(parents):
    """Build children lookup from parent indices."""
    children = {i: [] for i in range(len(parents))}
    for i, p in enumerate(parents):
        if p >= 0:
            children[p].append(i)
    return children


def get_rest_joints(betas):
    """Get SMPL-X zero-pose joint positions for correct bone lengths."""
    from hmr4d.utils.smplx_utils import make_smplx
    model = make_smplx("supermotion", use_pca=False, flat_hand_mean=True)
    with torch.no_grad():
        out = model(
            betas=betas[:1].float(),
            global_orient=torch.zeros(1, 3),
            body_pose=torch.zeros(1, 63),
            left_hand_pose=torch.zeros(1, 45),
            right_hand_pose=torch.zeros(1, 45),
            transl=torch.zeros(1, 3),
        )
    return out.joints[0, :55].cpu().numpy()


def compute_offsets(joints, parents):
    """Compute bone offsets: child position minus parent position."""
    offsets = np.zeros_like(joints)
    for i in range(len(joints)):
        if parents[i] < 0:
            offsets[i] = joints[i]
        else:
            offsets[i] = joints[i] - joints[parents[i]]
    return offsets


def dfs_order(root, children):
    """Depth-first traversal order (must match hierarchy and motion data)."""
    order = []
    def _visit(idx):
        order.append(idx)
        for c in children.get(idx, []):
            _visit(c)
    _visit(root)
    return order


def write_hierarchy(f, idx, offsets, children, names, parents, scale, depth=0):
    """Recursively write BVH HIERARCHY section."""
    tab = "\t" * depth
    name = names[idx]
    ox, oy, oz = offsets[idx] * scale
    tag = "ROOT" if parents[idx] < 0 else "JOINT"

    f.write(f"{tab}{tag} {name}\n{tab}{{\n")
    f.write(f"{tab}\tOFFSET {ox:.4f} {oy:.4f} {oz:.4f}\n")

    if parents[idx] < 0:
        f.write(f"{tab}\tCHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n")
    else:
        f.write(f"{tab}\tCHANNELS 3 Zrotation Xrotation Yrotation\n")

    kids = children.get(idx, [])
    if not kids:
        eo = offsets[idx] * 0.2 * scale
        f.write(f"{tab}\tEnd Site\n{tab}\t{{\n")
        f.write(f"{tab}\t\tOFFSET {eo[0]:.4f} {eo[1]:.4f} {eo[2]:.4f}\n")
        f.write(f"{tab}\t}}\n")
    else:
        for c in kids:
            write_hierarchy(f, c, offsets, children, names, parents, scale, depth + 1)

    f.write(f"{tab}}}\n")


def export_bvh(path, offsets, transl, rot_aa, names, parents, children, fps=30, scale=100.0):
    """
    Write BVH file.

    Args:
        path: output file path
        offsets: (N_joints, 3) rest pose bone offsets
        transl: (N_frames, 3) root translation per frame
        rot_aa: (N_frames, N_joints, 3) axis-angle rotation per joint
        names: joint name strings
        parents: parent index per joint
        children: children dict
        fps: frames per second
        scale: scale factor (100 = meters -> cm)
    """
    n_frames, n_joints = rot_aa.shape[:2]

    # Convert axis-angle to ZXY Euler angles (degrees)
    print(f"  Converting rotations ({n_frames} frames x {n_joints} joints)...")
    eulers = np.zeros((n_frames, n_joints, 3))
    for f in range(n_frames):
        for j in range(n_joints):
            aa = rot_aa[f, j]
            if np.linalg.norm(aa) > 1e-8:
                eulers[f, j] = Rotation.from_rotvec(aa).as_euler('ZXY', degrees=True)

    joint_order = dfs_order(0, children)

    with open(path, 'w') as fh:
        fh.write("HIERARCHY\n")
        write_hierarchy(fh, 0, offsets, children, names, parents, scale)

        fh.write("MOTION\n")
        fh.write(f"Frames: {n_frames}\n")
        fh.write(f"Frame Time: {1.0 / fps:.6f}\n")

        for f in range(n_frames):
            vals = []
            for j in joint_order:
                if parents[j] < 0:
                    tx, ty, tz = transl[f] * scale
                    vals.extend([tx, ty, tz])
                vals.extend(eulers[f, j].tolist())
            fh.write(" ".join(f"{v:.4f}" for v in vals) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Export GVHMR motion to BVH format")
    parser.add_argument("--results_dir", type=str, required=True,
                        help="Directory containing hmr4d_results.pt (and optionally hand_results.pt)")
    parser.add_argument("--output", type=str, default=None, help="Output BVH file path")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second (default: 30)")
    parser.add_argument("--body_only", action="store_true",
                        help="Export body joints only (22 joints, no hands/face)")
    parser.add_argument("--scale", type=float, default=100.0,
                        help="Scale factor: 100=centimeters (default), 1=meters")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    os.chdir(str(GVHMR_ROOT))

    # ── Load body results ─────────────────────────────────────────────────
    body_path = results_dir / "hmr4d_results.pt"
    if not body_path.exists():
        print(f"ERROR: {body_path} not found. Run inference first.")
        sys.exit(1)

    print(f"Loading body results: {body_path}")
    body = torch.load(str(body_path), map_location="cpu")
    params = body["smpl_params_global"]

    go = params["global_orient"].numpy().reshape(-1, 1, 3)
    bp = params["body_pose"].numpy().reshape(-1, 21, 3)
    tr = params.get("transl", torch.zeros(len(go), 3))
    if isinstance(tr, torch.Tensor):
        tr = tr.numpy()
    tr = tr.reshape(-1, 3)
    betas = params.get("betas", torch.zeros(1, 10))
    if isinstance(betas, torch.Tensor):
        pass  # keep as tensor for model forward
    L = len(go)

    # ── Load hand results if available ────────────────────────────────────
    hand_path = results_dir / "hand_results.pt"
    has_hands = hand_path.exists() and not args.body_only
    if has_hands:
        print(f"Loading hand results: {hand_path}")
        hr = torch.load(str(hand_path), map_location="cpu")
        lh = hr["left_hand_pose"].numpy().reshape(L, 15, 3)
        rh = hr["right_hand_pose"].numpy().reshape(L, 15, 3)

    # ── Build rotation array ─────────────────────────────────────────────
    if has_hands:
        n_joints = 55
        rot = np.zeros((L, 55, 3))
        rot[:, 0:1] = go
        rot[:, 1:22] = bp
        # joints 22-24 (jaw, eyes) stay zeros
        rot[:, 25:40] = lh
        rot[:, 40:55] = rh
        names = SMPLX_JOINT_NAMES
        parents = SMPLX_PARENTS
        label = "Full Body + Hands (55 joints)"
    else:
        n_joints = 22
        rot = np.zeros((L, 22, 3))
        rot[:, 0:1] = go
        rot[:, 1:22] = bp
        names = SMPLX_JOINT_NAMES[:22]
        parents = SMPLX_PARENTS[:22]
        label = "Body Only (22 joints)"

    children = build_children(parents)

    # ── Get rest pose for bone offsets ────────────────────────────────────
    print("Computing rest pose offsets...")
    try:
        rest = get_rest_joints(betas)[:n_joints]
    except Exception as e:
        print(f"  Warning: Could not compute rest pose ({e})")
        print(f"  Using approximate default offsets")
        rest = np.zeros((n_joints, 3))
        # Approximate SMPL-X offsets (meters)
        defaults = {
            0: [0, 0.91, 0], 1: [0.08, -0.06, 0], 2: [-0.08, -0.06, 0],
            3: [0, 0.12, 0], 4: [0, -0.42, 0], 5: [0, -0.42, 0],
            6: [0, 0.13, 0], 7: [0, -0.43, 0], 8: [0, -0.43, 0],
            9: [0, 0.14, 0], 10: [0, -0.06, 0.12], 11: [0, -0.06, 0.12],
            12: [0, 0.12, 0], 13: [0.02, 0.06, 0], 14: [-0.02, 0.06, 0],
            15: [0, 0.12, 0], 16: [0.12, 0, 0], 17: [-0.12, 0, 0],
            18: [0.26, 0, 0], 19: [-0.26, 0, 0], 20: [0.25, 0, 0],
            21: [-0.25, 0, 0],
        }
        for k, v in defaults.items():
            if k < n_joints:
                rest[k] = v

    offsets = compute_offsets(rest, parents)

    # ── Export ────────────────────────────────────────────────────────────
    if args.output:
        out_path = args.output
    else:
        suffix = "_body" if args.body_only else "_fullbody"
        out_path = str(results_dir / f"motion{suffix}.bvh")

    print(f"\nExporting BVH: {label}")
    print(f"  Frames: {L}, FPS: {args.fps}, Scale: {args.scale}x")
    export_bvh(out_path, offsets, tr, rot, names, parents, children, args.fps, args.scale)
    print(f"\n  Saved: {out_path}")
    print(f"\n--- How to use ---")
    print(f"  Blender:      File > Import > BVH (.bvh)")
    print(f"  Unity:        Drag .bvh into Assets, set Rig to Humanoid")
    print(f"  Unreal:       Import as Animation, retarget via IK Retargeter")
    print(f"  Maya:         File > Import > select BVH")
    print(f"  Retargeting:  Use Rokoko, AutoRig Pro, or Mixamo for bone mapping")


if __name__ == "__main__":
    main()
