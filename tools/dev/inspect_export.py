"""Inspect exported FBX animation."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

ext = argv[0].split('.')[-1].lower()
if ext == 'fbx':
    bpy.ops.import_scene.fbx(filepath=argv[0])
else:
    bpy.ops.wm.open_mainfile(filepath=argv[0])

s = bpy.context.scene
print(f"FRAME: start={s.frame_start} end={s.frame_end} fps={s.render.fps}")

for o in bpy.data.objects:
    if o.type != "ARMATURE":
        continue
    print(f"\nARM: {o.name}")
    print(f"  loc={tuple(round(v,4) for v in o.location)}")
    print(f"  scale={tuple(round(v,6) for v in o.scale)}")
    
    hips = o.pose.bones.get("mixamorig:Hips")
    if hips:
        for frame in [1, 60, 120]:
            if frame > s.frame_end:
                continue
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            print(f"  Hips@{frame} loc={tuple(round(v,2) for v in hips.location)}")
            wh = o.matrix_world @ hips.head
            wt = o.matrix_world @ hips.tail
            print(f"    world head={tuple(round(v,2) for v in wh)}")
            print(f"    world tail={tuple(round(v,2) for v in wt)}")
    
    # Check feet positions at frame 1
    for foot_name in ["mixamorig:LeftFoot", "mixamorig:RightFoot"]:
        foot = o.pose.bones.get(foot_name)
        if foot:
            bpy.context.scene.frame_set(1)
            bpy.context.view_layer.update()
            wh = o.matrix_world @ foot.head
            wt = o.matrix_world @ foot.tail
            print(f"  {foot_name}@1 world Z head={wh.z:.2f} tail={wt.z:.2f}")
