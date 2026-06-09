"""
Compares the pose matrix vs rest*basis product, and tests what rotation_quaternion
produces a standing character. This tells us if matrix_basis = correct local anim.
"""
import bpy, math
from mathutils import Matrix, Vector, Euler

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_anim.bvh(
    filepath=r"C:\Users\User\Documents\App\OPEN_OS\ESQUELETO_BAILARINA.bvh",
    rotate_mode='NATIVE', update_scene_fps=False, global_scale=0.01
)
bvh_arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')

bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

pb = bvh_arm.pose.bones['Pelvis']
Rb = pb.bone.matrix.to_3x3()
Ra = pb.matrix_basis.to_3x3()
Rpose = pb.matrix.to_3x3()

print("\n=== Pelvis frame 1 ===")
print(f"bone.matrix (rest, armature space):")
for r in Rb: print(f"  [{r[0]:+.3f} {r[1]:+.3f} {r[2]:+.3f}]")

print(f"\nmatrix_basis (local animation):")
for r in Ra: print(f"  [{r[0]:+.3f} {r[1]:+.3f} {r[2]:+.3f}]")

print(f"\npose matrix.to_3x3() (current frame, armature space):")
for r in Rpose: print(f"  [{r[0]:+.3f} {r[1]:+.3f} {r[2]:+.3f}]")

RbRa = Rb @ Ra
print(f"\nRb @ Ra (should equal pose.matrix):")
for r in RbRa: print(f"  [{r[0]:+.3f} {r[1]:+.3f} {r[2]:+.3f}]")

RaRb = Ra @ Rb
print(f"\nRa @ Rb (alternative order):")
for r in RaRb: print(f"  [{r[0]:+.3f} {r[1]:+.3f} {r[2]:+.3f}]")

# Check Rb^-1 @ Rpose
print(f"\nRb^-1 @ pose.matrix (should equal Ra if pose = Rb @ Ra):")
check = Rb.inverted() @ Rpose
for r in check: print(f"  [{r[0]:+.3f} {r[1]:+.3f} {r[2]:+.3f}]")

# Also check armature world matrix
mw = bvh_arm.matrix_world
print(f"\nBVH armature matrix_world diagonal (scale): {mw[0][0]:.4f} {mw[1][1]:.4f} {mw[2][2]:.4f}")
print(f"BVH armature rotation_euler: {[math.degrees(x) for x in bvh_arm.rotation_euler]}")

# World position via matrix_world @ pose_bone.head
world_head = mw @ pb.head
print(f"\nPelvis world head pos via mw @ head: X={world_head.x:.3f} Y={world_head.y:.3f} Z={world_head.z:.3f}")

# Mixamo head_local
bpy.ops.import_scene.fbx(filepath=r"C:\Users\User\Downloads\X Bot.fbx")
char = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o != bvh_arm)
hips = char.pose.bones.get('mixamorig:Hips')
if hips:
    print(f"\nMixamo Hips bone.head_local (rest head in armature space): {list(hips.bone.head_local)}")
    mw_inv = char.matrix_world.inverted()
    bvh_world = mw @ pb.head
    arm_local = (mw_inv @ bvh_world)
    print(f"bvh_world_pos in Mixamo armature space: {list(arm_local[:3])}")
    correct_loc = arm_local.to_3d() - hips.bone.head_local
    print(f"Correct pose_bone.location = armature_local - head_local: {list(correct_loc)}")
