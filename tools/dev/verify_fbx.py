"""Quick validation: import the exported FBX and dump bone names + animation range."""
import bpy, sys, os

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
fbx = argv[0]

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.import_scene.fbx(filepath=fbx)

arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if not arms:
    print("FAIL: no armature in FBX")
    sys.exit(1)
arm = arms[0]
bones = [b.name for b in arm.data.bones]
mix_bones = [n for n in bones if "mixamorig" in n.lower()]
print(f"VERIFY: armature='{arm.name}', total_bones={len(bones)}, mixamo_named={len(mix_bones)}")

# Animation range
if arm.animation_data and arm.animation_data.action:
    a = arm.animation_data.action
    print(f"VERIFY: action='{a.name}', frame_range={tuple(a.frame_range)}")
    n_fc = 0
    if hasattr(a, "fcurves"):
        n_fc = len(a.fcurves)
    elif hasattr(a, "layers"):
        for lyr in a.layers:
            for strip in lyr.strips:
                if hasattr(strip, "channelbag"):
                    for cb in strip.channelbags:
                        n_fc += len(cb.fcurves)
    print(f"VERIFY: fcurves={n_fc}")
else:
    print("FAIL: no animation data on armature")
    sys.exit(1)

# Sample bone lengths to confirm Mixamo proportions preserved
import math
def bl(b):
    return (b.head_local - b.tail_local).length
key_bones = ["mixamorig:Hips", "mixamorig:Spine", "mixamorig:LeftArm", "mixamorig:LeftForeArm",
             "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:Head"]
print("VERIFY: bone lengths (should match X Bot rest):")
for n in key_bones:
    b = arm.data.bones.get(n)
    if b:
        print(f"  {n}: {bl(b):.4f}")
    else:
        print(f"  {n}: MISSING")

# Sample pose at frame 1 / 60 / 130 to confirm it's not all rest
import bpy
for f in (1, 60, 130, 200):
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    pb = arm.pose.bones.get("mixamorig:LeftArm")
    if pb:
        q = pb.rotation_quaternion
        print(f"VERIFY: frame {f}  LeftArm quat=({q.w:.3f},{q.x:.3f},{q.y:.3f},{q.z:.3f})")

print("VERIFY: OK")
