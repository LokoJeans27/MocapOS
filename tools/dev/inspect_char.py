"""Inspect character armature dimensions."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

ext = argv[0].split('.')[-1].lower()
if ext == 'fbx':
    bpy.ops.import_scene.fbx(filepath=argv[0])
else:
    bpy.ops.wm.open_mainfile(filepath=argv[0])

for o in bpy.data.objects:
    if o.type != "ARMATURE":
        continue
    print(f"\n=== ARMATURE: {o.name} ===")
    print(f"  location={tuple(round(v,6) for v in o.location)}")
    print(f"  rotation_euler={tuple(round(v,6) for v in o.rotation_euler)}")
    print(f"  scale={tuple(round(v,6) for v in o.scale)}")
    
    # Bone bounds
    min_l = [float('inf')] * 3
    max_l = [-float('inf')] * 3
    for b in o.data.bones:
        for p in [b.head_local, b.tail_local]:
            for i in range(3):
                min_l[i] = min(min_l[i], p[i])
                max_l[i] = max(max_l[i], p[i])
    
    h_local = max_l[1] - min_l[1]
    print(f"  Local bounds Y (height): {h_local:.3f}")
    print(f"  World height estimate: {h_local * o.scale[1]:.4f}")
    
    hips = o.data.bones.get("mixamorig:Hips")
    if hips:
        hw = o.matrix_world @ hips.head_local
        print(f"  Hips head_local={tuple(round(v,3) for v in hips.head_local)}")
        print(f"  Hips world Z={hw.z:.4f}")
    print(f"  Bone count: {len(o.data.bones)}")
