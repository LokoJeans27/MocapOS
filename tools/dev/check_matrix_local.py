"""Check if matrix_local changed after alignment."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

for p in argv:
    ext = p.split('.')[-1].lower()
    if ext == 'fbx':
        bpy.ops.import_scene.fbx(filepath=p)

arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']

for arm in arms:
    print(f"\n=== {arm.name} ===")
    for bn in ["mixamorig:LeftArm", "mixamorig:LeftForeArm"]:
        b = arm.data.bones.get(bn)
        if b:
            m = b.matrix_local.to_3x3()
            print(f"{bn}: {tuple(round(v,3) for row in m for v in row)}")
            print(f"  head={tuple(round(v,2) for v in b.head_local)}")
            print(f"  tail={tuple(round(v,2) for v in b.tail_local)}")
