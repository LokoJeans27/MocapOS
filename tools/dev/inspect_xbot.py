"""Print X Bot armature world matrix and bone rest matrices for diagnosis."""
import bpy, sys, math
from mathutils import Matrix

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
fbx = argv[0]

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.import_scene.fbx(filepath=fbx)

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mw = arm.matrix_world
print(f"Armature: {arm.name}")
print(f"  world location: {tuple(mw.translation)}")
print(f"  world rotation (deg): {tuple(round(math.degrees(r),2) for r in mw.to_euler())}")
print(f"  world scale: {tuple(round(s,4) for s in mw.to_scale())}")
print(f"  matrix_world.to_3x3():")
mw3 = mw.to_3x3()
for r in range(3):
    print(f"    {[round(mw3[r][c],4) for c in range(3)]}")

for bn in ["mixamorig:Hips", "mixamorig:Spine", "mixamorig:LeftArm", "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:Head"]:
    b = arm.data.bones.get(bn)
    if b is None:
        print(f"  MISSING: {bn}")
        continue
    bm = b.matrix_local.to_3x3()
    print(f"  {bn} matrix_local (rest in armature):")
    for r in range(3):
        print(f"    {[round(bm[r][c],4) for c in range(3)]}")
    A = mw.to_3x3() @ bm
    print(f"  {bn} A = arm_world @ bone_rest (rest in WORLD):")
    for r in range(3):
        print(f"    {[round(A[r][c],4) for c in range(3)]}")
    h = b.head_local
    t = b.tail_local
    print(f"    head_local: {tuple(round(c,3) for c in h)}")
    print(f"    tail_local: {tuple(round(c,3) for c in t)}")
