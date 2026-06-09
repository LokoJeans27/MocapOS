import bpy, math
from mathutils import Matrix, Euler

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import BVH
bpy.ops.import_anim.bvh(
    filepath=r"C:\Users\User\Documents\App\OPEN_OS\ESQUELETO_BAILARINA.bvh",
    rotate_mode='NATIVE', update_scene_fps=False, global_scale=0.01
)
bvh_arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
bvh_arm.name = "BVH"

# Import Mixamo FBX
bpy.ops.import_scene.fbx(filepath=r"C:\Users\User\Downloads\X Bot.fbx")
char_arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name != "BVH")
char_arm.name = "CHAR"

bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

def m3str(m):
    rows = []
    for r in m:
        rows.append("  [" + "  ".join(f"{v:+.3f}" for v in r) + "]")
    return "\n".join(rows)

print("\n====== ARM OBJECT TRANSFORMS ======")
for arm, label in [(bvh_arm, "BVH"), (char_arm, "CHAR")]:
    r = arm.rotation_euler
    s = arm.scale
    print(f"{label}: rot=({math.degrees(r.x):.1f}, {math.degrees(r.y):.1f}, {math.degrees(r.z):.1f}) rot_mode={arm.rotation_mode}")

PAIRS = [
    ("Pelvis", "mixamorig:Hips"),
    ("Spine1", "mixamorig:Spine"),
    ("L_Hip",  "mixamorig:LeftUpLeg"),
    ("L_Collar","mixamorig:LeftShoulder"),
    ("L_Shoulder","mixamorig:LeftArm"),
]

print("\n====== BONE REST MATRICES (bone.matrix = armature-space rest orientation) ======")
for src, tgt in PAIRS:
    bvh_pb = bvh_arm.pose.bones.get(src)
    char_pb = char_arm.pose.bones.get(tgt)
    if not bvh_pb or not char_pb:
        print(f"MISSING: {src} or {tgt}")
        continue

    Rb = bvh_pb.bone.matrix
    Rm = char_pb.bone.matrix
    print(f"\n-- {src} (BVH) vs {tgt} (Mixamo) --")
    print(f"  BVH  bone.matrix (Y=bone_dir, armature space):")
    print(m3str(Rb))
    print(f"  CHAR bone.matrix:")
    print(m3str(Rm))

print("\n====== PELVIS matrix_basis at frame 1 ======")
pb = bvh_arm.pose.bones.get("Pelvis")
if pb:
    mb = pb.matrix_basis
    print(f"  rotation_mode: {pb.rotation_mode}")
    print(f"  rotation_euler: Z={math.degrees(pb.rotation_euler.z):.2f} X={math.degrees(pb.rotation_euler.x):.2f} Y={math.degrees(pb.rotation_euler.y):.2f}")
    print(f"  matrix_basis 3x3:")
    print(m3str(mb.to_3x3()))

print("\n====== SPINE1 matrix_basis at frame 1 ======")
pb = bvh_arm.pose.bones.get("Spine1")
if pb:
    print(f"  rotation_euler: Z={math.degrees(pb.rotation_euler.z):.2f} X={math.degrees(pb.rotation_euler.x):.2f} Y={math.degrees(pb.rotation_euler.y):.2f}")
    print(f"  matrix_basis 3x3:")
    print(m3str(pb.matrix_basis.to_3x3()))
