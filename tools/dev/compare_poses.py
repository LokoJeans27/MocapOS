"""Compare bone angles between two exported FBX files at a given frame."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
paths = argv

for p in paths:
    ext = p.split('.')[-1].lower()
    if ext == 'fbx':
        bpy.ops.import_scene.fbx(filepath=p)

arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"Found {len(arms)} armatures: {[a.name for a in arms]}")

frame = 60
bpy.context.scene.frame_set(frame)
bpy.context.view_layer.update()

bones_to_check = [
    "mixamorig:Hips", "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2",
    "mixamorig:LeftArm", "mixamorig:LeftForeArm", "mixamorig:LeftHand",
    "mixamorig:RightArm", "mixamorig:RightForeArm", "mixamorig:RightHand",
    "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
    "mixamorig:RightUpLeg", "mixamorig:RightLeg", "mixamorig:RightFoot",
]

print(f"\n=== Pose comparison at frame {frame} ===")
for bn in bones_to_check:
    vals = []
    for arm in arms:
        pb = arm.pose.bones.get(bn)
        if pb:
            q = pb.rotation_quaternion
            vals.append(tuple(round(v,3) for v in q))
        else:
            vals.append(None)
    if all(v is not None for v in vals):
        match = "OK" if all(abs(vals[0][i]-vals[1][i])<0.01 for i in range(4)) else "DIFF"
        print(f"{bn:25s}: {match}  {vals[0]}  vs  {vals[1]}")
