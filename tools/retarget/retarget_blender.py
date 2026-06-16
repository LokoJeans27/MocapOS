"""
Blender headless retargeting script.
Called by MocapOS GUI — not meant to be run directly.

Two input modes:

  (A) NPZ (preferred — direct from inference):
      blender --background --python retarget_blender.py -- \\
          --npz motion.npz --character "X Bot.fbx" --output out.fbx

      The skeleton from the start is the Mixamo armature in `--character`.
      Bone names and measurements come from X Bot.fbx; SMPL-X axis-angle
      rotations are applied directly with rest-pose change-of-basis.

  (B) BVH (legacy):
      blender --background --python retarget_blender.py -- \\
          --bvh motion.bvh --character model.fbx --output out.fbx

Supported output formats: .fbx  .glb  .gltf  .abc  .dae
"""

import bpy
import sys
import os
import math
from mathutils import Matrix, Vector, Euler, Quaternion

argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--bvh", default=None)
parser.add_argument("--npz", default=None)
parser.add_argument("--character", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--fps", type=int, default=30)
parser.add_argument("--axis_fix", default="none",
                    help="Axis convention debug knob. Default 'none' is correct "
                         "for SMPL-X (Y-up) → Mixamo armature-local (also Y-up). "
                         "Other options: conj_x90, conj_xneg90, pre_x90, pre_xneg90, "
                         "conj_x90_z180, conj_xneg90_z180, conj_x90_y180.")
args = parser.parse_args(argv)

if not args.bvh and not args.npz:
    print("ERROR: must provide --npz or --bvh")
    sys.exit(1)
if args.bvh and args.npz:
    print("ERROR: provide only one of --npz or --bvh")
    sys.exit(1)


# ── Bone mapping: SMPL-X joint name → Mixamo bone name ──────────────

BONE_MAP = {
    "Pelvis": "mixamorig:Hips",
    "Spine1": "mixamorig:Spine",
    "Spine2": "mixamorig:Spine1",
    "Spine3": "mixamorig:Spine2",
    "Neck": "mixamorig:Neck",
    "Head": "mixamorig:Head",
    "L_Collar": "mixamorig:LeftShoulder",
    "R_Collar": "mixamorig:RightShoulder",
    "L_Shoulder": "mixamorig:LeftArm",
    "R_Shoulder": "mixamorig:RightArm",
    "L_Elbow": "mixamorig:LeftForeArm",
    "R_Elbow": "mixamorig:RightForeArm",
    "L_Wrist": "mixamorig:LeftHand",
    "R_Wrist": "mixamorig:RightHand",
    "L_Hip": "mixamorig:LeftUpLeg",
    "R_Hip": "mixamorig:RightUpLeg",
    "L_Knee": "mixamorig:LeftLeg",
    "R_Knee": "mixamorig:RightLeg",
    "L_Ankle": "mixamorig:LeftFoot",
    "R_Ankle": "mixamorig:RightFoot",
    "L_Foot": "mixamorig:LeftToeBase",
    "R_Foot": "mixamorig:RightToeBase",
    # Fingers
    "L_Thumb1": "mixamorig:LeftHandThumb1",
    "L_Thumb2": "mixamorig:LeftHandThumb2",
    "L_Thumb3": "mixamorig:LeftHandThumb3",
    "L_Index1": "mixamorig:LeftHandIndex1",
    "L_Index2": "mixamorig:LeftHandIndex2",
    "L_Index3": "mixamorig:LeftHandIndex3",
    "L_Middle1": "mixamorig:LeftHandMiddle1",
    "L_Middle2": "mixamorig:LeftHandMiddle2",
    "L_Middle3": "mixamorig:LeftHandMiddle3",
    "L_Ring1": "mixamorig:LeftHandRing1",
    "L_Ring2": "mixamorig:LeftHandRing2",
    "L_Ring3": "mixamorig:LeftHandRing3",
    "L_Pinky1": "mixamorig:LeftHandPinky1",
    "L_Pinky2": "mixamorig:LeftHandPinky2",
    "L_Pinky3": "mixamorig:LeftHandPinky3",
    "R_Thumb1": "mixamorig:RightHandThumb1",
    "R_Thumb2": "mixamorig:RightHandThumb2",
    "R_Thumb3": "mixamorig:RightHandThumb3",
    "R_Index1": "mixamorig:RightHandIndex1",
    "R_Index2": "mixamorig:RightHandIndex2",
    "R_Index3": "mixamorig:RightHandIndex3",
    "R_Middle1": "mixamorig:RightHandMiddle1",
    "R_Middle2": "mixamorig:RightHandMiddle2",
    "R_Middle3": "mixamorig:RightHandMiddle3",
    "R_Ring1": "mixamorig:RightHandRing1",
    "R_Ring2": "mixamorig:RightHandRing2",
    "R_Ring3": "mixamorig:RightHandRing3",
    "R_Pinky1": "mixamorig:RightHandPinky1",
    "R_Pinky2": "mixamorig:RightHandPinky2",
    "R_Pinky3": "mixamorig:RightHandPinky3",
}


# ── SMPL-X kinematic tree (joint name → parent joint name) ─────────
# Used to forward-kinematic the per-joint LOCAL rotations into GLOBAL
# (world) rotations, so retargeting works for ANY character rest pose
# and ANY import orientation — not just Mixamo T-Pose / Y-up.

SMPLX_PARENTS = {
    "Pelvis": None,
    "L_Hip": "Pelvis", "R_Hip": "Pelvis", "Spine1": "Pelvis",
    "L_Knee": "L_Hip", "R_Knee": "R_Hip", "Spine2": "Spine1",
    "L_Ankle": "L_Knee", "R_Ankle": "R_Knee", "Spine3": "Spine2",
    "L_Foot": "L_Ankle", "R_Foot": "R_Ankle", "Neck": "Spine3",
    "L_Collar": "Spine3", "R_Collar": "Spine3", "Head": "Neck",
    "L_Shoulder": "L_Collar", "R_Shoulder": "R_Collar",
    "L_Elbow": "L_Shoulder", "R_Elbow": "R_Shoulder",
    "L_Wrist": "L_Elbow", "R_Wrist": "R_Elbow",
    "Jaw": "Head", "L_Eye": "Head", "R_Eye": "Head",
    "L_Index1": "L_Wrist", "L_Index2": "L_Index1", "L_Index3": "L_Index2",
    "L_Middle1": "L_Wrist", "L_Middle2": "L_Middle1", "L_Middle3": "L_Middle2",
    "L_Pinky1": "L_Wrist", "L_Pinky2": "L_Pinky1", "L_Pinky3": "L_Pinky2",
    "L_Ring1": "L_Wrist", "L_Ring2": "L_Ring1", "L_Ring3": "L_Ring2",
    "L_Thumb1": "L_Wrist", "L_Thumb2": "L_Thumb1", "L_Thumb3": "L_Thumb2",
    "R_Index1": "R_Wrist", "R_Index2": "R_Index1", "R_Index3": "R_Index2",
    "R_Middle1": "R_Wrist", "R_Middle2": "R_Middle1", "R_Middle3": "R_Middle2",
    "R_Pinky1": "R_Wrist", "R_Pinky2": "R_Pinky1", "R_Pinky3": "R_Pinky2",
    "R_Ring1": "R_Wrist", "R_Ring2": "R_Ring1", "R_Ring3": "R_Ring2",
    "R_Thumb1": "R_Wrist", "R_Thumb2": "R_Thumb1", "R_Thumb3": "R_Thumb2",
}


def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for c in bpy.data.collections:
        bpy.data.collections.remove(c)


def find_armature(name_hint=None):
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            if name_hint is None or name_hint in obj.name:
                return obj
    return None


def get_bone_names(armature):
    return [b.name for b in armature.data.bones]


def detect_bone_prefix(bone_names):
    for name in bone_names:
        if "Hips" in name:
            return name.split("Hips")[0]
    return ""


def resolve_target_name(mixamo_name, target_bones, target_prefix):
    """Find the actual bone name in target armature for a given mixamorig:* name."""
    if mixamo_name in target_bones:
        return mixamo_name
    bare = mixamo_name.replace("mixamorig:", "")
    candidate = target_prefix + bare
    if candidate in target_bones:
        return candidate
    return None


def axis_angle_to_matrix(aa):
    """3-vector axis-angle (Rodrigues) to 3x3 mathutils.Matrix."""
    angle = aa.length
    if angle < 1e-8:
        return Matrix.Identity(3)
    axis = aa / angle
    return Matrix.Rotation(angle, 3, axis)


def import_character(path):
    print("[1/5] Importing character...")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".dae":
        bpy.ops.wm.collada_import(filepath=path)
    elif ext == ".blend":
        # Append the first armature object from the .blend file
        imported_objs = []
        with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
            arm_names = [name for name in data_from.objects if name in data_from.armatures]
            if not arm_names:
                # fallback: import all objects and filter later
                arm_names = list(data_from.objects)
            for name in arm_names:
                data_to.objects.append(name)
                imported_objs.append(name)
        for name in imported_objs:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == 'ARMATURE' and obj.name not in bpy.context.collection.objects:
                bpy.context.collection.objects.link(obj)
    else:
        print(f"ERROR: Unsupported character format: {ext}")
        sys.exit(1)
    arm = find_armature()
    if arm is None:
        print("ERROR: No armature found in character file")
        sys.exit(1)
    arm.name = "Character"
    print(f"  Character armature: {arm.name} ({len(arm.data.bones)} bones)")

    # ── Normalize scale so every character has ~1.7m world height ──
    # Mixamo characters come in wildly different sizes (2m vs 83m).
    # We scale the armature object so the world height is ~1.7m, matching
    # SMPL-X proportions. The user can scale up/down afterwards in their DCC.
    #
    # NOTE: height must be measured in WORLD space (Blender is Z-up after
    # import). Measuring a fixed local axis breaks for characters whose FBX
    # imported without the +90°X correction (armature-local is Z-up), where
    # the local Y axis is depth, not height — that produced a bogus ~0.19m
    # "height" and a 9× over-scale on non-T-pose/Tripo rigs.
    bpy.context.view_layer.update()
    zs = []
    for b in arm.data.bones:
        for p in (b.head_local, b.tail_local):
            zs.append((arm.matrix_world @ p).z)
    h_world = (max(zs) - min(zs)) if zs else 0.0
    if h_world > 0.1 and abs(h_world - 1.7) > 0.3:
        norm = 1.7 / h_world
        arm.scale *= norm
        bpy.context.view_layer.update()
        print(f"  Normalized scale: world height {h_world:.2f}m → {1.7:.2f}m (factor {norm:.4f})")
    else:
        print(f"  World height: {h_world:.2f}m (no normalization needed)")

    return arm


def check_rest_pose(char_arm):
    """Informative only — user must provide A-pose character."""
    print("  (A-Pose character assumed — T-Pose will produce incorrect results)")


def export_result(char_arm, output_path, frame_start, frame_end):
    out_ext = os.path.splitext(output_path)[1].lower()
    print(f"[5/5] Exporting {out_ext.upper()}...")

    bpy.ops.object.select_all(action='DESELECT')
    char_arm.select_set(True)
    for child in char_arm.children:
        child.select_set(True)
    bpy.context.view_layer.objects.active = char_arm

    if out_ext == ".fbx":
        bpy.ops.export_scene.fbx(
            filepath=output_path,
            use_selection=True,
            bake_anim=True,
            bake_anim_use_all_bones=True,
            bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False,
            bake_anim_force_startend_keying=True,
            add_leaf_bones=False,
            apply_scale_options='FBX_SCALE_ALL',
            path_mode='COPY',
            embed_textures=True,
        )
    elif out_ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            use_selection=True,
            export_format='GLB' if out_ext == ".glb" else 'GLTF_SEPARATE',
            export_animations=True,
            export_anim_single_armature=True,
            export_current_frame=False,
        )
    elif out_ext == ".abc":
        bpy.ops.wm.alembic_export(
            filepath=output_path,
            selected=True,
            start=frame_start,
            end=frame_end,
            export_hair=False,
            export_particles=False,
            flatten=False,
        )
    elif out_ext == ".dae":
        bpy.ops.wm.collada_export(filepath=output_path, selected=True)
    else:
        print(f"  WARNING: Unknown extension '{out_ext}', defaulting to FBX")
        bpy.ops.export_scene.fbx(filepath=output_path, use_selection=True, bake_anim=True)


# ── NPZ MODE: direct from SMPL-X axis-angle ────────────────────────

def retarget_npz():
    import numpy as np
    print(f"\n{'='*60}")
    print(f"  MocapOS Retargeting (NPZ direct mode)")
    print(f"{'='*60}")
    print(f"  NPZ:       {args.npz}")
    print(f"  Character: {args.character}")
    print(f"  Output:    {args.output}")
    print()

    clean_scene()
    char_arm = import_character(args.character)
    check_rest_pose(char_arm)
    target_bones = get_bone_names(char_arm)
    target_prefix = detect_bone_prefix(target_bones)
    print(f"  Mixamo prefix detected: '{target_prefix}'")

    print("[2/5] Loading motion data...")
    data = np.load(args.npz, allow_pickle=False)
    rot_aa = data["rot_aa"]              # (L, J, 3) axis-angle per frame per joint
    transl = data["transl"]              # (L, 3)
    joint_names = [str(s) for s in data["joint_names"]]
    fps = int(data["fps"])
    L = int(data["n_frames"])
    n_joints = int(data["n_joints"])
    print(f"  Frames: {L}, Joints: {n_joints}, FPS: {fps}")

    print("[3/5] Building bone mapping...")
    # smplx_idx -> (mixamo bone name resolved in armature)
    idx_to_bone = {}
    for i, jname in enumerate(joint_names):
        if jname not in BONE_MAP:
            continue
        target = resolve_target_name(BONE_MAP[jname], target_bones, target_prefix)
        if target is not None:
            idx_to_bone[i] = target
    print(f"  Mapped {len(idx_to_bone)}/{n_joints} SMPL-X joints to Mixamo bones")
    if not idx_to_bone:
        print("ERROR: no bones mapped — check character is a Mixamo skeleton")
        sys.exit(1)

    # ── Precompute per-bone WORLD rest orientation ──────────────────────
    # The retarget is done entirely in Blender WORLD space so it is robust to:
    #   (a) the character's import orientation (armature-local Y-up vs Z-up —
    #       Mixamo downloads vs Tripo/auto-rigged FBX import differently), and
    #   (b) the character's rest pose (T-Pose vs A-Pose vs a relaxed/natural
    #       bind pose, e.g. arms-down).
    #
    # Method: forward-kinematic the SMPL-X LOCAL joint rotations into GLOBAL
    # (world) rotations G[i] in SMPL's Y-up world; map SMPL-Y-up → Blender-Z-up
    # with S = Rx(+90°) (the exact orientation a standard Mixamo FBX import
    # bakes onto the armature object); then drive each target bone's WORLD
    # orientation as  W(t) = (S·G[i]·S⁻¹) · W_rest  and convert to a pose-bone
    # matrix via Blender's own hierarchy solver (pose_bone.matrix), which makes
    # it independent of the bone's individual rest axes.
    S = Matrix.Rotation(math.radians(90), 3, 'X')   # SMPL Y-up → Blender Z-up
    S_inv = S.inverted()
    arm_R = char_arm.matrix_world.to_3x3()
    arm_R_inv = arm_R.inverted()

    # joint name ↔ index, and SMPL parent index per joint
    name_to_idx = {n: i for i, n in enumerate(joint_names)}
    parent_idx = []
    for n in joint_names:
        p = SMPLX_PARENTS.get(n, None)
        parent_idx.append(name_to_idx[p] if (p is not None and p in name_to_idx) else -1)

    # World rest 3x3 of each mapped target bone, plus a parent-first order.
    W_rest = {}
    depth = {}
    for idx, bone_name in idx_to_bone.items():
        b = char_arm.data.bones.get(bone_name)
        if b is None:
            continue
        W_rest[idx] = arm_R @ b.matrix_local.to_3x3()
        d = 0
        bb = b
        while bb.parent is not None:
            d += 1
            bb = bb.parent
        depth[idx] = d
    apply_order = sorted(idx_to_bone.keys(), key=lambda i: depth.get(i, 0))

    # ── Set scene frames ────────────────────────────────────────
    frame_start = 1
    frame_end = L
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end
    bpy.context.scene.render.fps = fps

    print("[4/5] Applying rotations (global-FK, rest/orientation independent)...")
    bpy.context.view_layer.objects.active = char_arm
    bpy.ops.object.mode_set(mode='POSE')
    for bone_name in idx_to_bone.values():
        pb = char_arm.pose.bones.get(bone_name)
        if pb:
            pb.rotation_mode = 'QUATERNION'

    pelvis_idx = name_to_idx.get("Pelvis", 0)
    hips_bone_name = idx_to_bone.get(pelvis_idx)

    char_mw_inv = char_arm.matrix_world.inverted()

    for f in range(L):
        bpy.context.scene.frame_set(frame_start + f)

        # Forward kinematics: LOCAL rotations → GLOBAL (world, SMPL Y-up).
        G = [None] * n_joints
        for i in range(n_joints):
            Ri = axis_angle_to_matrix(Vector(rot_aa[f, i].tolist()))
            p = parent_idx[i]
            G[i] = Ri if p < 0 else (G[p] @ Ri)

        # Apply per bone (parent-first) as a world-space orientation.
        for idx in apply_order:
            bone_name = idx_to_bone[idx]
            pb = char_arm.pose.bones.get(bone_name)
            if pb is None:
                continue
            W_t = (S @ G[idx] @ S_inv) @ W_rest[idx]      # desired Blender-world rot
            obj_rot = arm_R_inv @ W_t                      # armature/object space
            keep_loc = pb.matrix.to_translation()
            pb.matrix = Matrix.Translation(keep_loc) @ obj_rot.to_4x4()
            bpy.context.view_layer.update()
            pb.keyframe_insert(data_path="rotation_quaternion", frame=frame_start + f)

        # Root translation: SMPL transl (Y-up world m) → Blender world via S.
        if hips_bone_name:
            pb = char_arm.pose.bones.get(hips_bone_name)
            if pb is not None:
                world_pos = S @ Vector(transl[f].tolist())
                obj_pos = (char_mw_inv @ world_pos).to_3d()
                m = pb.matrix.copy()
                m.translation = obj_pos
                pb.matrix = m
                bpy.context.view_layer.update()
                pb.keyframe_insert(data_path="location", frame=frame_start + f)

        if (f + 1) % 60 == 0:
            print(f"  Frame {f+1}/{L}")

    bpy.ops.object.mode_set(mode='OBJECT')

    # ── Pass 2: Ground-snap. Find min foot world Z across all frames and lift
    # everything so the lowest point sits on Y=0. Without this, X Bot feet
    # float because its rest leg-length differs from SMPL-X betas.
    print("[4b] Ground-snap pass...")
    foot_bones = []
    for cand in ["mixamorig:LeftToeBase", "mixamorig:RightToeBase",
                 "mixamorig:LeftFoot", "mixamorig:RightFoot"]:
        rn = resolve_target_name(cand, target_bones, target_prefix)
        if rn:
            foot_bones.append(rn)
    print(f"  Tracking foot bones: {foot_bones}")

    bpy.context.view_layer.objects.active = char_arm
    bpy.ops.object.mode_set(mode='POSE')
    min_world_z = float("inf")
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        for bn in foot_bones:
            pb = char_arm.pose.bones.get(bn)
            if pb is None:
                continue
            world_head = char_arm.matrix_world @ pb.head
            world_tail = char_arm.matrix_world @ pb.tail
            z_min = min(world_head.z, world_tail.z)
            if z_min < min_world_z:
                min_world_z = z_min
    print(f"  min foot world Z across {frame_end-frame_start+1} frames: {min_world_z:.4f} m")

    bpy.ops.object.mode_set(mode='OBJECT')

    # Ground-snap by shifting the ARMATURE OBJECT in world Z (rest-pose &
    # orientation independent — no per-frame bone-local math that breaks on
    # rotated rest poses).
    if abs(min_world_z) > 1e-4:
        char_arm.location.z -= min_world_z
        print(f"  Lifted armature by {-min_world_z:.3f} m world Z (ground-snap)")

    # ── Center on origin at frame_start (zero only X/Y, keep Z) ──
    bpy.context.scene.frame_set(frame_start)
    bpy.context.view_layer.update()
    if hips_bone_name:
        hips_pb = char_arm.pose.bones.get(hips_bone_name)
        if hips_pb:
            world_head = char_arm.matrix_world @ hips_pb.head
            char_arm.location.x -= world_head.x
            char_arm.location.y -= world_head.y
            print(f"  Centered: X={world_head.x:.3f} Y={world_head.y:.3f} zeroed")

    export_result(char_arm, args.output, frame_start, frame_end)
    print(f"\n{'='*60}")
    print(f"  DONE! Saved to: {args.output}")
    print(f"{'='*60}\n")


# ── BVH MODE (legacy) ─────────────────────────────────────────────────
# For external BVH sources (Rokoko, XSens, etc.).  Imports the BVH as a
# temporary armature and copies rotations bone-by-bone with rest-pose
# change-of-basis.

def retarget_bvh():
    print(f"\n{'='*60}")
    print(f"  MocapOS Retargeting (BVH legacy mode)")
    print(f"{'='*60}")
    print(f"  BVH:       {args.bvh}")
    print(f"  Character: {args.character}")
    print(f"  Output:    {args.output}")
    print()

    clean_scene()
    char_arm = import_character(args.character)
    check_rest_pose(char_arm)
    target_bones = get_bone_names(char_arm)
    target_prefix = detect_bone_prefix(target_bones)

    print("[2/5] Importing BVH motion...")
    bpy.ops.import_anim.bvh(filepath=args.bvh, rotate_mode='NATIVE',
                            update_scene_fps=False, global_scale=0.01)

    bvh_arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj != char_arm:
            bvh_arm = obj
            break
    if bvh_arm is None:
        print("ERROR: No BVH armature imported")
        sys.exit(1)
    bvh_arm.name = "BVH_Source"
    source_bones = get_bone_names(bvh_arm)

    print("[3/5] Mapping bones...")
    mapping = {}
    for smpl_name, mixamo_name in BONE_MAP.items():
        if smpl_name not in source_bones:
            continue
        target = resolve_target_name(mixamo_name, target_bones, target_prefix)
        if target is not None:
            mapping[smpl_name] = target
    print(f"  Mapped {len(mapping)}/{len(BONE_MAP)} bones")
    if not mapping:
        print("ERROR: Could not map any bones.")
        sys.exit(1)

    print("[4/5] Retargeting (rest-pose corrected)...")
    if bvh_arm.animation_data and bvh_arm.animation_data.action:
        action = bvh_arm.animation_data.action
        frame_start = int(action.frame_range[0])
        frame_end = int(action.frame_range[1])
    else:
        frame_start = bpy.context.scene.frame_start
        frame_end = bpy.context.scene.frame_end
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end

    # Rest-pose change-of-basis: both in parent-local space
    T_map = {}
    for src, tgt in mapping.items():
        bvh_pb = bvh_arm.pose.bones.get(src)
        char_pb = char_arm.pose.bones.get(tgt)
        if bvh_pb and char_pb:
            A = char_pb.bone.matrix.to_3x3()
            B = bvh_pb.bone.matrix.to_3x3()
            T = B.inverted() @ A
            T_map[src] = (T, T.inverted())

    bpy.context.view_layer.objects.active = char_arm
    bpy.ops.object.mode_set(mode='POSE')
    for src, tgt in mapping.items():
        pb = char_arm.pose.bones.get(tgt)
        if pb:
            pb.rotation_mode = 'QUATERNION'

    bvh_mw = bvh_arm.matrix_world
    char_mw_inv = char_arm.matrix_world.inverted()

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        for src, tgt in mapping.items():
            bvh_pb = bvh_arm.pose.bones.get(src)
            char_pb = char_arm.pose.bones.get(tgt)
            if not bvh_pb or not char_pb:
                continue
            T, T_inv = T_map[src]
            Ra = bvh_pb.matrix_basis.to_3x3()
            corrected = T_inv @ Ra @ T
            char_pb.rotation_quaternion = corrected.to_quaternion()
            char_pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            if src == "Pelvis":
                bvh_world_pos = (bvh_mw @ bvh_pb.matrix).translation
                arm_local = (char_mw_inv @ bvh_world_pos).to_3d()
                char_pb.location = arm_local - char_pb.bone.head_local
                char_pb.keyframe_insert(data_path='location', frame=frame)
        if frame % 60 == 0:
            print(f"  Frame {frame}/{frame_end}...")

    bpy.ops.object.mode_set(mode='OBJECT')

    root_tgt = mapping.get("Pelvis")
    if root_tgt:
        bpy.context.scene.frame_set(frame_start)
        bpy.context.view_layer.update()
        hips_pb = char_arm.pose.bones.get(root_tgt)
        if hips_pb:
            world_head = char_arm.matrix_world @ hips_pb.head
            char_arm.location.x -= world_head.x
            char_arm.location.y -= world_head.y

    bpy.data.objects.remove(bvh_arm, do_unlink=True)
    export_result(char_arm, args.output, frame_start, frame_end)
    print(f"\n{'='*60}")
    print(f"  DONE! Saved to: {args.output}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if args.npz:
        retarget_npz()
    else:
        retarget_bvh()
