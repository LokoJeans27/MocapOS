"""Check animation status of armatures in a .blend."""
import bpy, sys
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
bpy.ops.wm.open_mainfile(filepath=argv[0])
s = bpy.context.scene
print(f"FRAME: start={s.frame_start} end={s.frame_end} fps={s.render.fps}")
for o in bpy.data.objects:
    if o.type != "ARMATURE":
        continue
    print(f"ARM: {o.name}")
    print(f"  loc={tuple(round(v,3) for v in o.location)}")
    print(f"  rot={tuple(round(v,3) for v in o.rotation_euler)}")
    print(f"  scale={tuple(round(v,4) for v in o.scale)}")
    a = o.animation_data
    if a is None:
        print("  no animation_data")
        continue
    if a.action is None:
        print("  no action")
        continue
    print(f"  ACTION: {a.action.name}, frame_range={tuple(a.action.frame_range)}")
    n_fc = 0
    if hasattr(a.action, "fcurves"):
        n_fc = len(a.action.fcurves)
    elif hasattr(a.action, "layers"):
        for lyr in a.action.layers:
            for strip in lyr.strips:
                if hasattr(strip, "channelbags"):
                    for cb in strip.channelbags:
                        n_fc += len(cb.fcurves)
    print(f"  fcurves: {n_fc}")
    # Sample a frame
    bpy.context.scene.frame_set(60)
    bpy.context.view_layer.update()
    hips = o.pose.bones.get("mixamorig:Hips")
    if hips:
        print(f"  Hips@60 location={tuple(round(v,3) for v in hips.location)}")
        print(f"  Hips@60 rot_quat={tuple(round(v,3) for v in hips.rotation_quaternion)}")
    larm = o.pose.bones.get("mixamorig:LeftArm")
    if larm:
        print(f"  LeftArm@60 rot_quat={tuple(round(v,3) for v in larm.rotation_quaternion)}")
