"""Compare 3D SMPL-X joint positions to Mixamo bone head positions.
Runs in Blender. Imports retargeted FBX, walks frames, queries bone heads
in armature-local space, compares to the SMPL-X joints loaded from .npz.
"""
import bpy
import sys
import os
import math
import argparse
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--joints_npz", required=True)
    p.add_argument("--frames", default="1,30,60,100,130,200")
    return p.parse_args(argv)


# SMPL-X 22-joint -> Mixamo bone (head position match)
# We compare the HEAD of the Mixamo bone to the SMPL-X joint position.
# Mixamo bone heads are slightly offset from SMPL-X joints, but the *relative*
# motion should match well.
SMPLX_TO_MIXAMO = {
    0: "mixamorig:Hips",         # Pelvis
    1: "mixamorig:LeftUpLeg",    # L_Hip
    2: "mixamorig:RightUpLeg",   # R_Hip
    3: "mixamorig:Spine",        # Spine1
    4: "mixamorig:LeftLeg",      # L_Knee
    5: "mixamorig:RightLeg",     # R_Knee
    6: "mixamorig:Spine1",       # Spine2
    7: "mixamorig:LeftFoot",     # L_Ankle
    8: "mixamorig:RightFoot",    # R_Ankle
    9: "mixamorig:Spine2",       # Spine3
    10: "mixamorig:LeftToeBase", # L_Foot
    11: "mixamorig:RightToeBase",# R_Foot
    12: "mixamorig:Neck",        # Neck
    13: "mixamorig:LeftShoulder",# L_Collar
    14: "mixamorig:RightShoulder",
    15: "mixamorig:Head",
    16: "mixamorig:LeftArm",     # L_Shoulder
    17: "mixamorig:RightArm",
    18: "mixamorig:LeftForeArm", # L_Elbow
    19: "mixamorig:RightForeArm",
    20: "mixamorig:LeftHand",    # L_Wrist
    21: "mixamorig:RightHand",
}


def main():
    args = parse_args()
    import numpy as np

    # Clean
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.fbx(filepath=args.fbx)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    print(f"FBX armature: {arm.name}, bones: {len(arm.data.bones)}")

    data = np.load(args.joints_npz)
    smplx_joints = data["joints"]  # (L, 22, 3) in Y-up world meters

    # SMPL-X joints have origin at Pelvis (well, Y=0 is ground actually).
    # We compare RELATIVE positions: subtract Pelvis to get joint-relative-to-pelvis.
    # Mixamo armature local is also Y-up, units cm. So we multiply SMPL-X by 100.

    frames = [int(x) for x in args.frames.split(",")]

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')

    # Use armature.matrix_world.inverted() to convert pose_bone world to arm-local.
    arm_mw_inv = arm.matrix_world.inverted()

    print("\nFrame | SMPL-X (Y-up, m, rel-pelvis) | Mixamo (arm-local, cm, rel-pelvis) | OK?")
    for f in frames:
        bpy.context.scene.frame_set(f + 1)  # blender frame_start = 1, smplx idx 0 = frame 1
        bpy.context.view_layer.update()

        # Pelvis reference
        smplx_pelv = smplx_joints[f, 0]
        hips = arm.pose.bones["mixamorig:Hips"]
        # pose_bone.head is in armature-local space (with pose)
        mix_pelv = hips.head

        worst_err = 0
        worst_name = ""
        for sidx, bn in SMPLX_TO_MIXAMO.items():
            sjoint = (smplx_joints[f, sidx] - smplx_pelv)  # m, Y-up, rel-pelvis
            sjoint_cm = Vector((float(sjoint[0])*100.0, float(sjoint[1])*100.0, float(sjoint[2])*100.0))
            pb = arm.pose.bones.get(bn)
            if pb is None:
                continue
            mix_pos = pb.head - mix_pelv  # arm-local, cm-units
            err = (mix_pos - sjoint_cm).length
            if err > worst_err:
                worst_err = err
                worst_name = bn

        print(f"  frame={f}  worst bone={worst_name}  err_cm={worst_err:.1f}")

    # Per-frame detailed for one frame
    detail_f = 60
    bpy.context.scene.frame_set(detail_f + 1)
    bpy.context.view_layer.update()
    smplx_pelv = smplx_joints[detail_f, 0]
    hips = arm.pose.bones["mixamorig:Hips"]
    mix_pelv = hips.head
    print(f"\nDetailed at frame {detail_f}:")
    print(f"  joint            smplx_xyz_cm           mixamo_xyz_cm           err")
    for sidx, bn in SMPLX_TO_MIXAMO.items():
        s = (smplx_joints[detail_f, sidx] - smplx_pelv) * 100.0
        sj = Vector((float(s[0]), float(s[1]), float(s[2])))
        pb = arm.pose.bones.get(bn)
        if pb is None:
            continue
        mix_pos = pb.head - mix_pelv
        err = (mix_pos - sj).length
        print(f"  {bn:30s} ({sj.x:6.1f},{sj.y:6.1f},{sj.z:6.1f}) "
              f"({mix_pos.x:6.1f},{mix_pos.y:6.1f},{mix_pos.z:6.1f})  err={err:5.1f}")


if __name__ == "__main__":
    main()
