"""Analyze rest-pose differences between X Bot and T-Pose."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

for p in argv:
    ext = p.split('.')[-1].lower()
    if ext == 'fbx':
        bpy.ops.import_scene.fbx(filepath=p)

arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']

bones = ["mixamorig:LeftArm", "mixamorig:LeftForeArm", "mixamorig:LeftHand",
         "mixamorig:RightArm", "mixamorig:RightForeArm", "mixamorig:RightHand",
         "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
         "mixamorig:RightUpLeg", "mixamorig:RightLeg", "mixamorig:RightFoot",
         "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2", "mixamorig:Neck"]

print("\n=== Bone direction comparison ===")
for bn in bones:
    dirs = []
    for arm in arms:
        b = arm.data.bones.get(bn)
        if b:
            d = (b.tail_local - b.head_local).normalized()
            dirs.append(tuple(round(v,4) for v in d))
        else:
            dirs.append(None)
    if all(d is not None for d in dirs):
        # Angle between directions
        import math
        d1 = dirs[0]
        d2 = dirs[1]
        dot = sum(d1[i]*d2[i] for i in range(3))
        angle = math.degrees(math.acos(max(-1, min(1, dot))))
        if angle > 5:
            print(f"{bn:25s}: angle={angle:.1f}°")
            print(f"  XBot:  {d1}")
            print(f"  TPos:  {d2}")
