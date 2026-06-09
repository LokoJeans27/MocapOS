"""Open test.blend and report scene contents (objects, cameras, render settings, frames)."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
blend = argv[0]
bpy.ops.wm.open_mainfile(filepath=blend)

s = bpy.context.scene
print(f"BLEND: file={blend}")
print(f"BLEND: render_engine={s.render.engine}")
print(f"BLEND: resolution={s.render.resolution_x}x{s.render.resolution_y}")
print(f"BLEND: frame_start={s.frame_start} frame_end={s.frame_end} fps={s.render.fps}")
print(f"BLEND: world_color={tuple(s.world.color) if s.world else None}")

print(f"BLEND: scene cameras:")
for o in bpy.data.objects:
    if o.type == 'CAMERA':
        loc = tuple(o.location)
        rot = tuple(round(r, 3) for r in o.rotation_euler)
        print(f"  CAMERA: name={o.name} loc={loc} rot_euler={rot} lens={o.data.lens}mm")

print(f"BLEND: lights:")
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        print(f"  LIGHT: name={o.name} type={o.data.type} energy={o.data.energy}")

print(f"BLEND: meshes/empties/armatures:")
for o in bpy.data.objects:
    if o.type in ('MESH', 'EMPTY', 'ARMATURE'):
        print(f"  {o.type}: name={o.name} loc={tuple(round(c,3) for c in o.location)}")

print(f"BLEND: collections:")
for c in bpy.data.collections:
    print(f"  COL: {c.name}  objects={[o.name for o in c.objects]}")
