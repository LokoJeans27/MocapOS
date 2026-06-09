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
    min_l = [float('inf')] * 3
    max_l = [-float('inf')] * 3
    for b in arm.data.bones:
        for p in [b.head_local, b.tail_local]:
            for i in range(3):
                min_l[i] = min(min_l[i], p[i])
                max_l[i] = max(max_l[i], p[i])
    h_local = max_l[1] - min_l[1]
    h_world = h_local * arm.scale[1]
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

    # ── Precompute per-bone REST-RELATIVE-TO-PARENT (3x3, in parent's frame) ──
    # SMPL-X output is in a Y-up world. Mixamo armature-LOCAL is also Y-up
    # (object has Rx+90° rotation). SMPL-X local rotation Ra[i] is the rotation
    # in the parent's frame (rest=identity in SMPL-X). So in Mixamo armature
    # local:
    #     pose_bone.matrix = parent_pose_matrix @ rest_in_parent @ matrix_basis
    #     We want pose_bone.matrix == world_rot_smplx[i] (FK in Y-up)
    #     and parent_pose_matrix == world_rot_smplx[parent]
    #     So:  matrix_basis = rest_in_parent⁻¹ @ Ra[i]
    # rest_in_parent for bone i = bone.matrix.to_3x3()  (Blender's "matrix"
    # property on Bone returns rest relative to parent, 3x3).
    A_map = {}
    for idx, bone_name in idx_to_bone.items():
        pb = char_arm.pose.bones.get(bone_name)
        if pb is None:
            continue
        A = pb.bone.matrix_local.to_3x3()  # bone rest in armature-local
        A_map[idx] = (A, A.inverted())

    # ── Set scene frames ────────────────────────────────────────
    frame_start = 1
    frame_end = L
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end
    bpy.context.scene.render.fps = fps

    print("[4/5] Applying rotations...")
    bpy.context.view_layer.objects.active = char_arm
    bpy.ops.object.mode_set(mode='POSE')
    for bone_name in idx_to_bone.values():
        pb = char_arm.pose.bones.get(bone_name)
        if pb:
            pb.rotation_mode = 'QUATERNION'

    # Find pelvis/hips bone for translation
    pelvis_idx = joint_names.index("Pelvis") if "Pelvis" in joint_names else 0
    hips_bone_name = idx_to_bone.get(pelvis_idx)

    char_mw = char_arm.matrix_world
    char_mw_inv = char_mw.inverted()

    # ── Axis fix: empirical knob. Pick whichever produces correct poses.
    Rx90 = Matrix.Rotation(math.radians(90), 3, 'X')
    Rxneg90 = Matrix.Rotation(math.radians(-90), 3, 'X')
    Rz180 = Matrix.Rotation(math.radians(180), 3, 'Z')
    Ry180 = Matrix.Rotation(math.radians(180), 3, 'Y')
    Rx180 = Matrix.Rotation(math.radians(180), 3, 'X')
    I3 = Matrix.Identity(3)

    fix = args.axis_fix
    if fix == "none":
        Q_root, Q_root_inv, Q_chld, Q_chld_inv, Q_tr = I3, I3, I3, I3, I3
    elif fix == "conj_x90":
        Q_root, Q_chld, Q_tr = Rx90, Rx90, Rx90
        Q_root_inv, Q_chld_inv = Q_root.inverted(), Q_chld.inverted()
    elif fix == "conj_xneg90":
        Q_root, Q_chld, Q_tr = Rxneg90, Rxneg90, Rxneg90
        Q_root_inv, Q_chld_inv = Q_root.inverted(), Q_chld.inverted()
    elif fix == "pre_x90":
        # apply R only to root rotation (pre-mult), leave children alone, rotate transl
        Q_root = Rx90; Q_root_inv = I3
        Q_chld = I3; Q_chld_inv = I3
        Q_tr = Rx90
    elif fix == "pre_xneg90":
        Q_root = Rxneg90; Q_root_inv = I3
        Q_chld = I3; Q_chld_inv = I3
        Q_tr = Rxneg90
    elif fix == "conj_x90_z180":
        # conjugate by (Rz180 @ Rx90) — useful if facing direction is flipped
        Q = Rz180 @ Rx90
        Q_root = Q_chld = Q
        Q_root_inv = Q_chld_inv = Q.inverted()
        Q_tr = Q
    elif fix == "conj_xneg90_z180":
        Q = Rz180 @ Rxneg90
        Q_root = Q_chld = Q
        Q_root_inv = Q_chld_inv = Q.inverted()
        Q_tr = Q
    elif fix == "conj_x90_y180":
        Q = Ry180 @ Rx90
        Q_root = Q_chld = Q
        Q_root_inv = Q_chld_inv = Q.inverted()
        Q_tr = Q
    else:
        Q_root, Q_root_inv, Q_chld, Q_chld_inv, Q_tr = I3, I3, I3, I3, I3

    print(f"  Axis fix: {fix}")

    for f in range(L):
        bpy.context.scene.frame_set(frame_start + f)

        for idx, bone_name in idx_to_bone.items():
            aa = Vector(rot_aa[f, idx].tolist())
            Ra_in = axis_angle_to_matrix(aa)
            if idx == pelvis_idx:
                Ra = Q_root @ Ra_in @ Q_root_inv
            else:
                Ra = Q_chld @ Ra_in @ Q_chld_inv
            A, A_inv = A_map[idx]
            corrected = A_inv @ Ra @ A
            pb = char_arm.pose.bones.get(bone_name)
            if pb is None:
                continue
            pb.rotation_quaternion = corrected.to_quaternion()
            pb.keyframe_insert(data_path="rotation_quaternion", frame=frame_start + f)

        if hips_bone_name:
            pb = char_arm.pose.bones.get(hips_bone_name)
            if pb is not None:
                tx, ty, tz = transl[f].tolist()
                # SMPL-X transl is Y-up world meters. Convert to Blender Z-up
                # (Y→Z, Z→-Y), then to armature-local via char_mw_inv.
                # Works for any armature scale/orientation.
                world_pos_zup = Vector((tx, -tz, ty))
                world_pos_zup = Q_tr @ world_pos_zup
                arm_local = (char_mw_inv @ world_pos_zup).to_3d()
                pb.location = arm_local - pb.bone.head_local
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

    if hips_bone_name and abs(min_world_z) > 1e-4:
        # Convert a "shift world Z by -min_world_z" into the armature-local
        # delta vector — works for any armature scale & rotation.
        world_shift = Vector((0.0, 0.0, -min_world_z))
        # Use the 3x3 (rotation+scale) inverse — translation cancels.
        delta_arm_local = char_arm.matrix_world.to_3x3().inverted() @ world_shift
        hips_pb = char_arm.pose.bones[hips_bone_name]
        for frame in range(frame_start, frame_end + 1):
            bpy.context.scene.frame_set(frame)
            hips_pb.location += delta_arm_local
            hips_pb.keyframe_insert(data_path="location", frame=frame)
        print(f"  Lifted Hips by {tuple(round(v,2) for v in delta_arm_local)} (arm-local) "
              f"= {-min_world_z:.3f} m world Z")

    bpy.ops.object.mode_set(mode='OBJECT')

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
