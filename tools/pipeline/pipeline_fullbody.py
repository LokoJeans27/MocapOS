"""
GVHMR + HaMeR Integration: Full body + hand motion recovery
Combines GVHMR body prediction with HaMeR hand prediction for complete motion capture.
Includes wrist rotation fix using forward kinematics.
"""

import sys
import os
import subprocess
import cv2
import torch
# Disable cuDNN to avoid "Invalid handle" errors on some GPU configurations
torch.backends.cudnn.enabled = False
import numpy as np
import argparse
from pathlib import Path
from tqdm import tqdm
from pytorch3d.transforms import axis_angle_to_matrix, matrix_to_axis_angle, rotation_6d_to_matrix

# Add project roots to path
GVHMR_ROOT = Path(__file__).resolve().parents[2]
HAMER_ROOT = GVHMR_ROOT / "hamer_lib"
sys.path.insert(0, str(GVHMR_ROOT))
sys.path.insert(0, str(HAMER_ROOT))

from hmr4d.utils.pylogger import Log
from hmr4d.utils.video_io_utils import get_video_lwh, read_video_np, save_video, merge_videos_horizontal, get_writer, get_video_reader
from hmr4d.utils.net_utils import detach_to_cpu, to_cuda
from hmr4d.utils.smplx_utils import make_smplx
from hmr4d.utils.vis.renderer import Renderer, get_global_cameras_static, get_ground_params_from_points
from hmr4d.utils.geo.hmr_cam import create_camera_sensor
from hmr4d.utils.geo_transform import apply_T_on_points, compute_T_ayfz2ay
from einops import einsum

CRF = 23


def fix_video_rotation(video_path):
    """
    Re-encode video if it has rotation metadata or is portrait/MOV.
    imageio does NOT auto-apply rotation, so we must bake it in with ffmpeg.
    """
    video_path = str(video_path)
    # Derive ffmpeg/ffprobe paths from Python executable
    python_dir = Path(sys.executable).parent
    ffprobe = str(python_dir / "Library" / "bin" / "ffprobe.exe")
    ffmpeg = str(python_dir / "Library" / "bin" / "ffmpeg.exe")

    if not Path(ffprobe).exists() or not Path(ffmpeg).exists():
        Log.info("[Video] ffprobe/ffmpeg not found, skipping rotation check")
        return video_path

    try:
        import json as _json
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", video_path],
            capture_output=True, text=True
        )
        data = _json.loads(result.stdout)
        needs_fix = False
        reason = ""

        if video_path.lower().endswith('.mov'):
            needs_fix = True
            reason = "MOV file"

        for stream in data.get("streams", []):
            if stream.get("codec_type") != "video":
                continue
            # Legacy rotation tag
            rot = stream.get("tags", {}).get("rotate", "0")
            if rot != "0":
                needs_fix = True
                reason = f"rotation tag {rot}"
            # Modern display matrix
            for sd in stream.get("side_data_list", []):
                sd_type = sd.get("side_data_type", "")
                if "display" in sd_type.lower() or "rotation" in sd_type.lower():
                    r = sd.get("rotation", 0)
                    if r != 0:
                        needs_fix = True
                        reason = f"display rotation {r}"
            # Portrait detection
            w = int(stream.get("width", 0))
            h = int(stream.get("height", 0))
            if w > 0 and h > 0 and h > w:
                needs_fix = True
                reason = f"portrait {w}x{h}"

        if needs_fix:
            fixed = str(Path(video_path).with_suffix("")) + "_fixed.mp4"
            if Path(fixed).exists():
                Log.info(f"[Video] Using existing fixed video: {fixed}")
                return fixed
            Log.info(f"[Video] Re-encoding ({reason})...")
            subprocess.run(
                [ffmpeg, "-y", "-i", video_path, "-c:v", "libx264", "-crf", "18", "-an", fixed],
                capture_output=True
            )
            if Path(fixed).exists():
                Log.info(f"[Video] Fixed -> {fixed}")
                return fixed
    except Exception as e:
        Log.info(f"[Video] Rotation check failed: {e}")

    return video_path


# ========================================================================
# Hand pose post-processing: temporal smoothing + angle clamping
# ========================================================================

def smooth_hand_temporal(hand_pose, window=3):
    """
    Temporal smoothing for hand poses using quaternion moving average.
    Handles quaternion double-cover problem (q vs -q represent same rotation).

    Args:
        hand_pose: (L, 45) tensor of axis-angle hand poses
        window: smoothing window size (must be odd, default 3 = ±1 frame)

    Returns:
        smoothed hand_pose of same shape and device
    """
    from scipy.spatial.transform import Rotation

    L, D = hand_pose.shape
    if L < window or window < 2:
        return hand_pose

    # Convert to quaternions: (L, 45) -> (L*15, 3) -> quats (L*15, 4)
    rots = Rotation.from_rotvec(hand_pose.reshape(-1, 3).cpu().numpy())
    quats = rots.as_quat()  # (L*15, 4), format [x, y, z, w]
    n_joints = D // 3
    quats = quats.reshape(L, n_joints, 4)

    half = window // 2
    smoothed_quats = np.zeros_like(quats)

    for i in range(L):
        start = max(0, i - half)
        end = min(L, i + half + 1)
        w_quats = quats[start:end].copy()  # (w, n_joints, 4)

        # Fix double cover: make all quaternions in window have same sign as first
        ref = w_quats[0:1]  # (1, n_joints, 4)
        dot = np.sum(w_quats * ref, axis=-1)  # (w, n_joints)
        flip = dot < 0
        w_quats[flip] *= -1

        # Average quaternion per joint
        avg = w_quats.mean(axis=0)  # (n_joints, 4)
        norms = np.linalg.norm(avg, axis=-1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        avg = avg / norms

        smoothed_quats[i] = avg

    # Convert back to axis-angle
    smoothed_rots = Rotation.from_quat(smoothed_quats.reshape(-1, 4))
    smoothed_aa = smoothed_rots.as_rotvec().reshape(L, D)

    return torch.from_numpy(smoothed_aa).to(hand_pose.device, hand_pose.dtype)


def clamp_hand_angles(hand_pose, max_angle=1.8):
    """
    Clamp hand joint rotations to physiologically reasonable limits.
    max_angle: maximum rotation in radians (~103 degrees).

    Args:
        hand_pose: (L, 45) tensor of axis-angle hand poses

    Returns:
        clamped hand_pose of same shape
    """
    orig_shape = hand_pose.shape
    hand_pose_3 = hand_pose.reshape(-1, 3)
    angles = torch.norm(hand_pose_3, dim=1, keepdim=True)

    # Scale down angles that exceed max_angle
    scale = torch.ones_like(angles)
    mask = angles > max_angle
    scale[mask] = max_angle / angles[mask]

    hand_pose_3 = hand_pose_3 * scale
    return hand_pose_3.reshape(orig_shape)


def freeze_and_interpolate_hand_pose(hand_pose, confidences, conf_threshold=0.3, max_gap=10):
    """
    Freeze hand pose to last known good pose for low-confidence frames,
    and interpolate (slerp) through short gaps between valid segments.

    Args:
        hand_pose: (L, 45) tensor of axis-angle hand poses
        confidences: (L,) numpy array of confidence scores (e.g. ViTPose wrist conf)
        conf_threshold: minimum confidence to consider a frame valid
        max_gap: maximum gap length (in frames) to interpolate across.
                 Longer gaps are frozen to the last valid pose.

    Returns:
        processed hand_pose of same shape and device
    """
    from scipy.spatial.transform import Rotation, Slerp

    L = hand_pose.shape[0]
    if L == 0:
        return hand_pose

    conf = np.asarray(confidences)
    valid = conf >= conf_threshold

    if valid.all():
        return hand_pose

    # Convert to quaternions: (L, 45) -> (L*15, 3) -> quats (L*15, 4)
    rots = Rotation.from_rotvec(hand_pose.reshape(-1, 3).cpu().numpy())
    quats = rots.as_quat().reshape(L, 15, 4)  # [x, y, z, w]

    def fix_continuity(q_seq):
        """Ensure quaternion continuity by flipping sign when dot < 0."""
        for t in range(1, len(q_seq)):
            if np.sum(q_seq[t] * q_seq[t - 1]) < 0:
                q_seq[t] *= -1
        return q_seq

    result_quats = np.zeros_like(quats)

    for j in range(15):
        q = quats[:, j, :].copy()
        q = fix_continuity(q)

        valid_idx = np.where(valid)[0]
        if len(valid_idx) == 0:
            # No valid frames at all -> keep original (will be zero or garbage, but no data)
            result_quats[:, j, :] = q
            continue

        first_valid = valid_idx[0]
        last_valid = valid_idx[-1]

        # Fill start gap: hold first valid pose
        result_quats[:first_valid, j, :] = q[first_valid]

        # Fill end gap: hold last valid pose
        result_quats[last_valid:, j, :] = q[last_valid]

        # Process internal gaps between valid segments
        for k in range(len(valid_idx) - 1):
            start = valid_idx[k]
            end = valid_idx[k + 1]
            gap = end - start - 1

            result_quats[start, j, :] = q[start]

            if gap <= 0:
                continue

            if gap <= max_gap:
                # Short gap: spherical linear interpolation (slerp)
                q_start = q[start]
                q_end = q[end]
                if np.dot(q_start, q_end) < 0:
                    q_end = -q_end

                key_times = [0, gap + 1]
                key_rots = Rotation.from_quat([q_start, q_end])
                slerp = Slerp(key_times, key_rots)
                interp_times = np.arange(1, gap + 1)
                interp_quats = slerp(interp_times).as_quat()
                result_quats[start + 1:end, j, :] = interp_quats
            else:
                # Long gap: freeze to last valid pose (don't guess across long occlusions)
                result_quats[start + 1:end, j, :] = q[start]

        result_quats[last_valid, j, :] = q[last_valid]

    # Convert back to axis-angle
    result_rots = Rotation.from_quat(result_quats.reshape(-1, 4))
    result_aa = result_rots.as_rotvec().reshape(L, 45)

    return torch.from_numpy(result_aa).to(hand_pose.device, hand_pose.dtype)


# Mirror matrix for left hand correction (flip X axis)
MIRROR = torch.diag(torch.tensor([-1.0, 1.0, 1.0]))

# SMPL-X body_pose index -> skeleton joint mapping:
# body_pose[:, idx] = skeleton joint (idx+1)
# Kinematic chain to left wrist:  0->3->6->9->13->16->18->20
# body_pose indices:               2  5  8  12  15  17  19
# Kinematic chain to right wrist: 0->3->6->9->14->17->19->21
# body_pose indices:               2  5  8  13  16  18  20
LEFT_ARM_CHAIN = [2, 5, 8, 12, 15, 17]   # spine1, spine2, spine3, l_collar, l_shoulder, l_elbow
RIGHT_ARM_CHAIN = [2, 5, 8, 13, 16, 18]  # spine1, spine2, spine3, r_collar, r_shoulder, r_elbow
LEFT_WRIST_IDX = 19   # body_pose index for L_Wrist
RIGHT_WRIST_IDX = 20  # body_pose index for R_Wrist


def load_hamer_model(device="cuda"):
    """Load HaMeR hand model."""
    from hamer.models import load_hamer, DEFAULT_CHECKPOINT, CACHE_DIR_HAMER

    # Check multiple possible locations for checkpoints
    possible_paths = [
        HAMER_ROOT / "_DATA" / "hamer_ckpts" / "checkpoints" / "hamer.ckpt",
        Path(CACHE_DIR_HAMER) / "hamer_ckpts" / "checkpoints" / "hamer.ckpt",
        Path("_DATA") / "hamer_ckpts" / "checkpoints" / "hamer.ckpt",
    ]

    ckpt_path = None
    for p in possible_paths:
        if p.exists():
            ckpt_path = str(p)
            break

    if ckpt_path is None:
        Log.info("[HaMeR] Checkpoint not found. Downloading...")
        from hamer.models import download_models
        download_models(str(HAMER_ROOT / "_DATA"))
        ckpt_path = str(HAMER_ROOT / "_DATA" / "hamer_ckpts" / "checkpoints" / "hamer.ckpt")

    Log.info(f"[HaMeR] Loading from {ckpt_path}")
    model, model_cfg = load_hamer(ckpt_path)
    model = model.to(device)
    model.eval()
    return model, model_cfg


def detect_hands_from_vitpose(vitpose_kp2d, bbx_xyxy, frame_shape):
    """
    Extract hand bounding boxes from ViTPose keypoints.
    ViTPose COCO17 keypoints: 9=left_wrist, 10=right_wrist
    We use wrist position + offset to create hand bounding boxes.

    Args:
        vitpose_kp2d: (L, 17, 3) - keypoints with confidence
        bbx_xyxy: (L, 4) - person bounding box
        frame_shape: (H, W)

    Returns:
        left_hand_boxes: (L, 4) or None per frame
        right_hand_boxes: (L, 4) or None per frame
        left_confs: (L,) wrist confidence per frame
        right_confs: (L,) wrist confidence per frame
    """
    L = vitpose_kp2d.shape[0]
    H, W = frame_shape

    left_hands = []
    right_hands = []
    left_confs = []
    right_confs = []

    for i in range(L):
        kps = vitpose_kp2d[i]  # (17, 3) - x, y, conf

        # Left wrist = keypoint 9, Left elbow = keypoint 7
        lw_conf = kps[9, 2] if kps.shape[1] > 2 else 1.0
        rw_conf = kps[10, 2] if kps.shape[1] > 2 else 1.0

        # Person bbox size for scaling hand box
        person_w = bbx_xyxy[i, 2] - bbx_xyxy[i, 0]
        hand_size = max(person_w * 0.15, 40)  # Hand box size relative to person

        # Left hand (wrist keypoint 9)
        if lw_conf > 0.3:
            lx, ly = kps[9, 0], kps[9, 1]
            # Extend from wrist towards fingers (away from elbow)
            if kps[7, 2] > 0.3:  # elbow visible
                dx = lx - kps[7, 0]
                dy = ly - kps[7, 1]
                norm = max(np.sqrt(dx*dx + dy*dy), 1e-6)
                dx, dy = dx/norm, dy/norm
                cx = lx + dx * hand_size * 0.4
                cy = ly + dy * hand_size * 0.4
            else:
                cx, cy = lx, ly

            x1 = max(0, cx - hand_size)
            y1 = max(0, cy - hand_size)
            x2 = min(W, cx + hand_size)
            y2 = min(H, cy + hand_size)
            left_hands.append([x1, y1, x2, y2])
        else:
            left_hands.append(None)
        left_confs.append(float(lw_conf))

        # Right hand (wrist keypoint 10)
        if rw_conf > 0.3:
            rx, ry = kps[10, 0], kps[10, 1]
            if kps[8, 2] > 0.3:  # elbow visible
                dx = rx - kps[8, 0]
                dy = ry - kps[8, 1]
                norm = max(np.sqrt(dx*dx + dy*dy), 1e-6)
                dx, dy = dx/norm, dy/norm
                cx = rx + dx * hand_size * 0.4
                cy = ry + dy * hand_size * 0.4
            else:
                cx, cy = rx, ry

            x1 = max(0, cx - hand_size)
            y1 = max(0, cy - hand_size)
            x2 = min(W, cx + hand_size)
            y2 = min(H, cy + hand_size)
            right_hands.append([x1, y1, x2, y2])
        else:
            right_hands.append(None)
        right_confs.append(float(rw_conf))

    return left_hands, right_hands, np.array(left_confs), np.array(right_confs)


def predict_hands_for_video(video_path, left_boxes, right_boxes, left_confs, right_confs,
                             hamer_model, hamer_cfg, device="cuda"):
    """
    Run HaMeR on each frame for detected hands.

    Returns:
        left_hand_pose: (L, 45) axis-angle finger poses
        right_hand_pose: (L, 45) axis-angle finger poses
        left_wrist_orient: (L, 3, 3) wrist orientation rotation matrices
        right_wrist_orient: (L, 3, 3) wrist orientation rotation matrices
        left_confs_out: (L,) confidence per frame (ViTPose wrist conf, 0 if HaMeR failed)
        right_confs_out: (L,) confidence per frame
    """
    from hamer.datasets.vitdet_dataset import ViTDetDataset
    from hamer.utils import recursive_to

    reader = get_video_reader(video_path)
    L = len(left_boxes)

    left_poses = torch.zeros(L, 45)
    right_poses = torch.zeros(L, 45)
    left_wrist_orient = torch.zeros(L, 3, 3)
    right_wrist_orient = torch.zeros(L, 3, 3)
    left_confs_out = left_confs.copy()
    right_confs_out = right_confs.copy()

    Log.info("[HaMeR] Predicting hand poses + wrist orientations...")

    for i, frame in tqdm(enumerate(reader), total=L, desc="HaMeR Hands"):
        frame_bgr = frame[:, :, ::-1].copy()  # RGB (imageio) to BGR (cv2 format for HaMeR)

        for hand_type, boxes, poses, wrist_orients, confs_out in [
            ("left", left_boxes, left_poses, left_wrist_orient, left_confs_out),
            ("right", right_boxes, right_poses, right_wrist_orient, right_confs_out)
        ]:
            if boxes[i] is None:
                confs_out[i] = 0.0
                continue

            is_right = 1.0 if hand_type == "right" else 0.0
            bbox = np.array([boxes[i]], dtype=np.float32)

            try:
                dataset = ViTDetDataset(
                    hamer_cfg,
                    frame_bgr,
                    boxes=bbox,
                    right=np.array([is_right], dtype=np.float32),
                    rescale_factor=2.5,
                )

                batch = dataset[0]
                batch_t = {}
                for k, v in batch.items():
                    if isinstance(v, np.ndarray):
                        batch_t[k] = torch.tensor(v).unsqueeze(0).to(device)
                    elif isinstance(v, torch.Tensor):
                        batch_t[k] = v.unsqueeze(0).to(device)

                with torch.no_grad():
                    out = hamer_model(batch_t)

                # hand_pose is (1, 15, 3, 3) rotation matrices -> convert to axis-angle (1, 15, 3)
                hand_rotmats = out["pred_mano_params"]["hand_pose"].cpu()
                hand_aa = matrix_to_axis_angle(hand_rotmats)  # CPU to avoid NVRTC issues

                # global_orient is (1, 1, 3, 3) rotation matrix -> wrist orientation
                wrist_go = out["pred_mano_params"]["global_orient"].cpu().reshape(3, 3)

                if hand_type == "left":
                    # HaMeR flips left hands and processes as right hand.
                    # Mirror correction for axis-angle: (ax, ay, az) -> (ax, -ay, -az)
                    hand_aa[:, :, 1] = -hand_aa[:, :, 1]
                    hand_aa[:, :, 2] = -hand_aa[:, :, 2]
                    # Mirror correction for rotation matrix: M @ R @ M
                    wrist_go = MIRROR @ wrist_go @ MIRROR

                poses[i] = hand_aa.reshape(1, 45)
                wrist_orients[i] = wrist_go
                # Keep original ViTPose confidence as proxy for this frame's quality

            except Exception as e:
                Log.info(f"[HaMeR] Warning frame {i} {hand_type}: {e}")
                confs_out[i] = 0.0  # Mark as invalid
                pass  # Keep zeros for failed frames

    reader.close()

    # Stats
    l_nz = (left_wrist_orient.abs().sum(dim=(1, 2)) > 0.1).sum().item()
    r_nz = (right_wrist_orient.abs().sum(dim=(1, 2)) > 0.1).sum().item()
    Log.info(f"[HaMeR] Wrist orientations - Left: {l_nz}/{L}, Right: {r_nz}/{L}")

    return left_poses, right_poses, left_wrist_orient, right_wrist_orient, left_confs_out, right_confs_out


def _clamp_wrist_aa(aa, bp_fallback, max_angle=0.5, comp_max=0.4):
    """Clamp wrist axis-angle. If out of bounds, return body fallback."""
    angle = torch.norm(aa)
    if angle > max_angle:
        return bp_fallback, True
    # Per-component clamp: no single axis should exceed comp_max
    if torch.any(torch.abs(aa) > comp_max):
        return bp_fallback, True
    return aa, False


def compute_wrist_rotations(incam_params, left_wrist_orient, right_wrist_orient,
                            wrist_max_angle=0.5, wrist_comp_max=0.4):
    """
    Compute local wrist rotations from HaMeR's global_orient using forward kinematics.

    If the resulting local wrist angle exceeds wrist_max_angle (radians) or any
    individual axis-angle component exceeds wrist_comp_max, we reject the HaMeR
    prediction and fall back to GVHMR's body wrist rotation.

    Args:
        incam_params: dict with global_orient (L,1,3) and body_pose (L,63) in camera space
        left_wrist_orient: (L, 3, 3) HaMeR wrist orientation for left hand
        right_wrist_orient: (L, 3, 3) HaMeR wrist orientation for right hand
        wrist_max_angle: maximum allowed local wrist rotation in radians (~28° default)
        wrist_comp_max: maximum allowed per-component axis-angle in radians (~23° default)

    Returns:
        left_wrist_aa: (L, 3) axis-angle local wrist rotation for left hand
        right_wrist_aa: (L, 3) axis-angle local wrist rotation for right hand
    """
    go = incam_params["global_orient"].cpu().reshape(-1, 3)
    bp = incam_params["body_pose"].cpu().reshape(-1, 21, 3)
    L = len(go)

    # Convert all local rotations to matrices (batch)
    R_root = axis_angle_to_matrix(go)  # (L, 3, 3)
    R_body = axis_angle_to_matrix(bp.reshape(-1, 3)).reshape(L, 21, 3, 3)  # (L, 21, 3, 3)

    left_wrist_aa = torch.zeros(L, 3)
    right_wrist_aa = torch.zeros(L, 3)
    n_rejected_left = 0
    n_rejected_right = 0

    for i in range(L):
        # Left arm: compute G_elbow via FK chain
        if left_wrist_orient[i].abs().sum() > 0.1:
            G = R_root[i]
            for bp_idx in LEFT_ARM_CHAIN:
                G = G @ R_body[i, bp_idx]
            # Local wrist = G_elbow^{-1} @ HaMeR_wrist_global
            R_local = G.T @ left_wrist_orient[i]
            aa = matrix_to_axis_angle(R_local.unsqueeze(0))[0]
            aa, rejected = _clamp_wrist_aa(aa, bp[i, LEFT_WRIST_IDX], wrist_max_angle, wrist_comp_max)
            left_wrist_aa[i] = aa
            if rejected:
                n_rejected_left += 1
        else:
            # Keep GVHMR's original wrist rotation
            left_wrist_aa[i] = bp[i, LEFT_WRIST_IDX]

        # Right arm: same process
        if right_wrist_orient[i].abs().sum() > 0.1:
            G = R_root[i]
            for bp_idx in RIGHT_ARM_CHAIN:
                G = G @ R_body[i, bp_idx]
            R_local = G.T @ right_wrist_orient[i]
            aa = matrix_to_axis_angle(R_local.unsqueeze(0))[0]
            aa, rejected = _clamp_wrist_aa(aa, bp[i, RIGHT_WRIST_IDX], wrist_max_angle, wrist_comp_max)
            right_wrist_aa[i] = aa
            if rejected:
                n_rejected_right += 1
        else:
            right_wrist_aa[i] = bp[i, RIGHT_WRIST_IDX]

    Log.info(f"[Wrist FK] Computed local wrist rotations for {L} frames")
    if n_rejected_left > 0 or n_rejected_right > 0:
        Log.info(f"[Wrist FK] Rejected (fallback to body wrist) - Left: {n_rejected_left}, Right: {n_rejected_right}")
    return left_wrist_aa, right_wrist_aa


def apply_wrist_fix(params, left_wrist_aa, right_wrist_aa):
    """Replace body_pose wrist rotations with HaMeR-derived ones."""
    bp = params["body_pose"].clone()
    L = bp.shape[0]
    bp = bp.reshape(L, 21, 3)
    bp[:, LEFT_WRIST_IDX, :] = left_wrist_aa.to(bp.device)
    bp[:, RIGHT_WRIST_IDX, :] = right_wrist_aa.to(bp.device)
    params["body_pose"] = bp.reshape(L, 63)
    return params


def render_incam_with_hands(cfg, left_hand_pose, right_hand_pose,
                             left_wrist_aa=None, right_wrist_aa=None):
    """Render in-camera view with hand poses and wrist rotation fix."""
    incam_video_path = Path(str(cfg.paths.incam_video).replace(".mp4", "_hands.mp4"))

    pred = torch.load(cfg.paths.hmr4d_results)
    smplx_model = make_smplx("supermotion", use_pca=False, flat_hand_mean=True).cuda()
    faces_smplx = smplx_model.faces

    # Build SMPL-X params WITH hand poses
    params = {k: v.cuda() if isinstance(v, torch.Tensor) else v
              for k, v in pred["smpl_params_incam"].items()}
    params.pop("left_hand_pose", None)
    params.pop("right_hand_pose", None)
    params["left_hand_pose"] = left_hand_pose.float().cuda()
    params["right_hand_pose"] = right_hand_pose.float().cuda()

    # Apply wrist rotation fix
    if left_wrist_aa is not None and right_wrist_aa is not None:
        params = apply_wrist_fix(params, left_wrist_aa, right_wrist_aa)

    smplx_out = smplx_model(**params)
    pred_c_verts = smplx_out.vertices

    # Render
    video_path = cfg.video_path
    length, width, height = get_video_lwh(video_path)
    K = pred["K_fullimg"][0]

    renderer = Renderer(width, height, device="cuda", faces=faces_smplx, K=K, bin_size=0)
    reader = get_video_reader(video_path)

    writer = get_writer(str(incam_video_path), fps=30, crf=CRF)
    for i, img_raw in tqdm(enumerate(reader), total=length, desc="Rendering Incam+Hands"):
        img = renderer.render_mesh(pred_c_verts[i].cuda(), img_raw, [0.8, 0.8, 0.8])
        writer.write_frame(img)
    writer.close()
    reader.close()

    return str(incam_video_path)


def render_global_with_hands(cfg, left_hand_pose, right_hand_pose,
                              left_wrist_aa=None, right_wrist_aa=None):
    """Render global view with hand poses and wrist rotation fix."""
    global_video_path = Path(str(cfg.paths.global_video).replace(".mp4", "_hands.mp4"))

    pred = torch.load(cfg.paths.hmr4d_results)
    smplx_model = make_smplx("supermotion", use_pca=False, flat_hand_mean=True).cuda()
    faces_smplx = smplx_model.faces
    J_regressor = torch.load("hmr4d/utils/body_model/smpl_neutral_J_regressor.pt").cuda()
    smplx2smpl = torch.load("hmr4d/utils/body_model/smplx2smpl_sparse.pt").cuda()

    # Build SMPL-X params WITH hand poses
    params = {k: v.cuda() if isinstance(v, torch.Tensor) else v
              for k, v in pred["smpl_params_global"].items()}
    params.pop("left_hand_pose", None)
    params.pop("right_hand_pose", None)
    params["left_hand_pose"] = left_hand_pose.float().cuda()
    params["right_hand_pose"] = right_hand_pose.float().cuda()

    # Apply wrist rotation fix
    if left_wrist_aa is not None and right_wrist_aa is not None:
        params = apply_wrist_fix(params, left_wrist_aa, right_wrist_aa)

    smplx_out = smplx_model(**params)
    pred_ay_verts = smplx_out.vertices  # Full SMPL-X (L, 10475, 3)
    pred_ay_verts_smpl = torch.stack([torch.matmul(smplx2smpl, v_) for v_ in pred_ay_verts])

    def move_to_start_point_face_z(verts, verts_smpl):
        verts = verts.clone()
        verts_smpl = verts_smpl.clone()
        offset = einsum(J_regressor, verts_smpl[0], "j v, v i -> j i")[0]
        offset[1] = verts[:, :, [1]].min()
        verts = verts - offset
        verts_smpl = verts_smpl - offset
        T_ay2ayfz = compute_T_ayfz2ay(einsum(J_regressor, verts_smpl[[0]], "j v, l v i -> l j i"), inverse=True)
        verts = apply_T_on_points(verts, T_ay2ayfz)
        verts_smpl = apply_T_on_points(verts_smpl, T_ay2ayfz)
        return verts, verts_smpl

    verts_glob, verts_glob_smpl = move_to_start_point_face_z(pred_ay_verts, pred_ay_verts_smpl)
    joints_glob = einsum(J_regressor, verts_glob_smpl, "j v, l v i -> l j i")
    global_R, global_T, global_lights = get_global_cameras_static(
        verts_glob.cpu(), beta=2.0, cam_height_degree=20, target_center_height=1.0,
    )

    video_path = cfg.video_path
    length, width, height = get_video_lwh(video_path)
    _, _, K = create_camera_sensor(width, height, 24)

    renderer = Renderer(width, height, device="cuda", faces=faces_smplx, K=K, bin_size=0)
    scale, cx, cz = get_ground_params_from_points(joints_glob[:, 0], verts_glob)
    renderer.set_ground(scale * 1.5, cx, cz)
    color = torch.ones(3).float().cuda() * 0.8

    writer = get_writer(str(global_video_path), fps=30, crf=CRF)
    for i in tqdm(range(length), desc="Rendering Global+Hands"):
        cameras = renderer.create_camera(global_R[i], global_T[i])
        img = renderer.render_with_ground(verts_glob[[i]], color[None], cameras, global_lights)
        writer.write_frame(img)
    writer.close()

    return str(global_video_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GVHMR + HaMeR: Full body + hands motion recovery")
    parser.add_argument("--video", type=str, required=True, help="Input video path")
    parser.add_argument("--output_root", type=str, default=None)
    parser.add_argument("-s", "--static_cam", action="store_true")
    parser.add_argument("--f_mm", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skip_body", action="store_true", help="Skip GVHMR body (use existing results)")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    assert video_path.exists(), f"Video not found: {video_path}"

    # Set CWD to GVHMR root for relative path resolution
    os.chdir(GVHMR_ROOT)

    # Fix video rotation (MOV files, portrait, phone recordings)
    fixed = fix_video_rotation(str(video_path))
    video_path = Path(fixed).resolve()

    # ===== Step 1: Run GVHMR body prediction ===== #
    if not args.skip_body:
        Log.info("=" * 60)
        Log.info("[Step 1/3] Running GVHMR body prediction...")
        Log.info("=" * 60)
        cmd = [sys.executable, "-u", "tools/pipeline/pipeline.py", "--video", str(video_path), "--skip_render"]
        if args.static_cam:
            cmd.append("-s")
        if args.f_mm:
            cmd += ["--f_mm", str(args.f_mm)]
        if args.output_root:
            cmd += ["--output_root", args.output_root]
        if args.verbose:
            cmd.append("--verbose")
        subprocess.run(cmd, cwd=str(GVHMR_ROOT), check=True)

    # Build paths manually (avoid complex Hydra config resolution)
    output_root = args.output_root or "outputs/results"
    video_stem = video_path.stem
    output_dir = Path(output_root) / video_stem
    preprocess_dir = output_dir / "preprocess"

    class CfgPaths:
        pass
    class Cfg:
        pass

    cfg = Cfg()
    cfg.video_path = str(output_dir / "0_input_video.mp4")
    cfg.output_dir = str(output_dir)
    cfg.static_cam = args.static_cam
    cfg.paths = CfgPaths()
    cfg.paths.bbx = str(preprocess_dir / "bbx.pt")
    cfg.paths.vitpose = str(preprocess_dir / "vitpose.pt")
    cfg.paths.hmr4d_results = str(output_dir / "hmr4d_results.pt")
    cfg.paths.incam_video = str(output_dir / "1_incam.mp4")
    cfg.paths.global_video = str(output_dir / "2_global.mp4")

    # ===== Step 2: Run HaMeR hand prediction ===== #
    Log.info("=" * 60)
    Log.info("[Step 2/3] Running HaMeR hand prediction...")
    Log.info("=" * 60)

    hamer_model, hamer_cfg = load_hamer_model()

    # Load ViTPose keypoints from GVHMR preprocessing
    vitpose = torch.load(cfg.paths.vitpose).numpy()  # (L, 17, 3)
    bbx_xyxy = torch.load(cfg.paths.bbx)["bbx_xyxy"].numpy()  # (L, 4)

    length, width, height = get_video_lwh(cfg.video_path)

    # Detect hands from body keypoints
    left_boxes, right_boxes, left_confs, right_confs = detect_hands_from_vitpose(vitpose, bbx_xyxy, (height, width))

    n_left = sum(1 for b in left_boxes if b is not None)
    n_right = sum(1 for b in right_boxes if b is not None)
    Log.info(f"[HaMeR] Detected hands - Left: {n_left}/{length}, Right: {n_right}/{length}")

    # Predict hand poses + wrist orientations
    left_hand_pose, right_hand_pose, left_wrist_orient, right_wrist_orient, left_confs, right_confs = \
        predict_hands_for_video(cfg.video_path, left_boxes, right_boxes, left_confs, right_confs,
                                hamer_model, hamer_cfg)

    # ===== Post-process: freeze/interpolate -> smooth -> clamp ===== #
    Log.info("[HaMeR] Post-processing hands: freeze bad frames -> interpolate gaps -> smooth -> clamp...")
    left_hand_pose = freeze_and_interpolate_hand_pose(left_hand_pose, left_confs, conf_threshold=0.3, max_gap=10)
    right_hand_pose = freeze_and_interpolate_hand_pose(right_hand_pose, right_confs, conf_threshold=0.3, max_gap=10)

    left_hand_pose = smooth_hand_temporal(left_hand_pose, window=3)
    right_hand_pose = smooth_hand_temporal(right_hand_pose, window=3)
    left_hand_pose = clamp_hand_angles(left_hand_pose, max_angle=1.8)
    right_hand_pose = clamp_hand_angles(right_hand_pose, max_angle=1.8)
    Log.info("[HaMeR] Post-processing complete")

    # Save hand results
    hand_results_path = Path(cfg.paths.hmr4d_results).parent / "hand_results.pt"
    torch.save({
        "left_hand_pose": left_hand_pose,
        "right_hand_pose": right_hand_pose,
        "left_wrist_orient": left_wrist_orient,
        "right_wrist_orient": right_wrist_orient,
        "left_confidences": left_confs,
        "right_confidences": right_confs,
    }, str(hand_results_path))
    Log.info(f"[HaMeR] Hand results saved to {hand_results_path}")

    # Free HaMeR GPU memory
    del hamer_model
    torch.cuda.empty_cache()

    # ===== Compute wrist rotations via forward kinematics ===== #
    Log.info("[Wrist FK] Computing wrist rotations from HaMeR orientations...")
    pred = torch.load(cfg.paths.hmr4d_results, map_location="cpu")
    left_wrist_aa, right_wrist_aa = compute_wrist_rotations(
        pred["smpl_params_incam"], left_wrist_orient, right_wrist_orient
    )

    # Smooth wrists temporally + re-clamp to avoid popping after smoothing
    Log.info("[Wrist FK] Smoothing + re-clamping wrist rotations...")
    left_wrist_aa = smooth_hand_temporal(left_wrist_aa, window=5)
    right_wrist_aa = smooth_hand_temporal(right_wrist_aa, window=5)
    left_wrist_aa = clamp_hand_angles(left_wrist_aa, max_angle=0.5)
    right_wrist_aa = clamp_hand_angles(right_wrist_aa, max_angle=0.5)
    Log.info("[Wrist FK] Wrist post-processing complete")

    # ===== Step 3: Re-render with hands + wrist fix ===== #
    Log.info("=" * 60)
    Log.info("[Step 3/3] Rendering with hand poses + wrist rotation fix...")
    Log.info("=" * 60)

    incam_path = render_incam_with_hands(cfg, left_hand_pose, right_hand_pose,
                                          left_wrist_aa, right_wrist_aa)
    global_path = render_global_with_hands(cfg, left_hand_pose, right_hand_pose,
                                            left_wrist_aa, right_wrist_aa)

    # Merge videos (ensure ffmpeg is in PATH)
    python_dir = Path(sys.executable).parent
    conda_env_dir = python_dir
    ffmpeg_dir = str(conda_env_dir / "Library" / "bin")
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    merged_path = str(Path(cfg.output_dir) / f"{video_stem}_fullbody_hands.mp4")
    merge_videos_horizontal([incam_path, global_path], merged_path)

    # Cleanup obsolete body-only renders to save disk space
    output_dir_path = Path(cfg.output_dir)
    keep_names = {
        Path(cfg.video_path).name,               # 0_input_video.mp4
        Path(incam_path).name,                   # 1_incam_hands.mp4
        Path(global_path).name,                  # 2_global_hands.mp4
        Path(merged_path).name,                  # REF_*_fullbody_hands.mp4
    }
    for mp4_file in output_dir_path.glob("*.mp4"):
        if mp4_file.name not in keep_names:
            Log.info(f"[Cleanup] Removing obsolete render: {mp4_file.name}")
            mp4_file.unlink()

    Log.info("=" * 60)
    Log.info(f"[Done!] Output: {merged_path}")
    Log.info(f"  Incam:  {incam_path}")
    Log.info(f"  Global: {global_path}")
    Log.info(f"  Merged: {merged_path}")
    Log.info("=" * 60)
