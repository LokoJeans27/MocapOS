"""Compare rest-pose matrices between two exported FBX files."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
paths = argv

for p in paths:
    ext = p.split('.')[-1].lower()
    if ext == 'fbx':
        bpy.ops.import_scene.fbx(filepath=p)

arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']

bones_to_check = [
    "mixamorig:Hips", "mixamorig:Spine", "mixamorig:LeftArm",
    "mixamorig:LeftForeArm", "mixamorig:LeftUpLeg", "mixamorig:LeftLeg",
]

print(f"\n=== Rest-pose matrix_local 3x3 comparison ===")
for bn in bones_to_check:
    vals = []
    for arm in arms:
        b = arm.data.bones.get(bn)
        if b:
            m = b.matrix_local.to_3x3()
            # Flatten for comparison
            vals.append(tuple(round(v,4) for row in m for v in row))
        else:
            vals.append(None)
    if all(v is not None for v in vals):
        match = "OK" if all(abs(vals[0][i]-vals[1][i])<0.01 for i in range(9)) else "DIFF"
        print(f"{bn:25s}: {match}")
        print(f"  A: {vals[0]}")
        print(f"  B: {vals[1]}")
