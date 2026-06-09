import bpy, math

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_scene.fbx(filepath=r"C:\Users\User\Downloads\X Bot.fbx")
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        r = obj.rotation_euler
        s = obj.scale
        print(f"FBX '{obj.name}': rot=({math.degrees(r.x):.1f}, {math.degrees(r.y):.1f}, {math.degrees(r.z):.1f}) scale=({s.x:.4f}, {s.y:.4f}, {s.z:.4f})")

bpy.ops.import_anim.bvh(
    filepath=r"C:\Users\User\Documents\App\OPEN_OS\ESQUELETO_BAILARINA.bvh",
    rotate_mode='NATIVE', update_scene_fps=False, global_scale=0.01
)
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE' and 'Armature' in obj.name:
        r = obj.rotation_euler
        s = obj.scale
        print(f"BVH '{obj.name}': rot=({math.degrees(r.x):.1f}, {math.degrees(r.y):.1f}, {math.degrees(r.z):.1f}) scale=({s.x:.4f}, {s.y:.4f}, {s.z:.4f})")
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        for bname in ['Pelvis', 'Spine1', 'Spine2', 'L_Hip', 'L_Knee']:
            pb = obj.pose.bones.get(bname)
            if pb:
                re = pb.rotation_euler
                print(f"  [{bname}] local_rot=({math.degrees(re.x):.2f}, {math.degrees(re.y):.2f}, {math.degrees(re.z):.2f}) mode={pb.rotation_mode}")

# Also check the Mixamo armature bone rotations at rest
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE' and 'Armature' not in obj.name:
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        for bname in ['mixamorig:Hips', 'mixamorig:Spine', 'mixamorig:LeftUpLeg']:
            pb = obj.pose.bones.get(bname)
            if pb:
                re = pb.rotation_euler
                rl = pb.rotation_quaternion
                print(f"  Mixamo [{bname}] rot_mode={pb.rotation_mode}")
