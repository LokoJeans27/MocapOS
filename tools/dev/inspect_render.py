"""Debug render setup for T-Pose aligned."""
import bpy

# Clean and import
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_scene.fbx(filepath="C:/Users/User/Desktop/test_tpose_aligned.fbx")

arm = None
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
        break

bpy.context.scene.frame_set(60)
bpy.context.view_layer.update()

print(f"Armature: {arm.name}")
print(f"  location={tuple(arm.location)}")
print(f"  scale={tuple(arm.scale)}")

hips = arm.pose.bones.get("mixamorig:Hips")
if hips:
    wh = arm.matrix_world @ hips.head
    print(f"  Hips world head={tuple(wh)}")
    print(f"  Hips world tail={tuple(arm.matrix_world @ hips.tail)}")

# Check mesh bounds
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"  Meshes: {len(meshes)}")
for m in meshes:
    print(f"    {m.name}: loc={tuple(m.location)} scale={tuple(m.scale)}")
    # World bounds
    verts = [m.matrix_world @ v.co for v in m.data.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    print(f"    bounds X={min(xs):.2f}..{max(xs):.2f} Y={min(ys):.2f}..{max(ys):.2f} Z={min(zs):.2f}..{max(zs):.2f}")
