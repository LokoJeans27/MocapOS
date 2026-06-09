import bpy, sys
p = sys.argv[-1]
bpy.ops.import_scene.fbx(filepath=p)
arm = [o for o in bpy.context.selected_objects if o.type=='ARMATURE'][0]
print(f"Object: {arm.name}")
print(f"  rotation_euler: {tuple(arm.rotation_euler)}")
print(f"  rotation_quaternion: {tuple(arm.rotation_quaternion)}")
print(f"  scale: {tuple(arm.scale)}")
