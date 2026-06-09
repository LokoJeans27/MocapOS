"""List all bone names in the armature(s) of a .blend file."""
import bpy, sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
bpy.ops.wm.open_mainfile(filepath=argv[0])

for o in bpy.data.objects:
    if o.type == "ARMATURE":
        print(f"ARM: {o.name}  bones={len(o.data.bones)}  rotation={tuple(round(r,3) for r in o.rotation_euler)}  scale={tuple(round(s,4) for s in o.scale)}")
        for b in o.data.bones:
            print(f"  BONE: {b.name}")
