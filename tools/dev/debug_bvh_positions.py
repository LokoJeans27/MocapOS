import bpy, math

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_anim.bvh(
    filepath=r"C:\Users\User\Documents\App\OPEN_OS\ESQUELETO_BAILARINA.bvh",
    rotate_mode='NATIVE', update_scene_fps=False, global_scale=0.01
)

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

print("\n=== BVH bone world positions at frame 1 (Z=height in Blender Z-up) ===")
chain = ['Pelvis','Spine1','Spine2','Spine3','Neck','Head',
         'L_Hip','L_Knee','L_Ankle',
         'L_Shoulder','L_Elbow','L_Wrist']
for name in chain:
    pb = arm.pose.bones.get(name)
    if pb:
        w = arm.matrix_world @ pb.head
        print(f"  {name:15s}  X={w.x:+.3f}  Y={w.y:+.3f}  Z(height)={w.z:+.3f} m")

# Distance between key points
p_hips = arm.matrix_world @ arm.pose.bones['Pelvis'].head
p_neck = arm.matrix_world @ arm.pose.bones['Neck'].head
p_head = arm.matrix_world @ arm.pose.bones['Head'].head
p_ankle = arm.matrix_world @ arm.pose.bones['L_Ankle'].head

print(f"\n=== Proportions ===")
print(f"  Hip height:    {p_hips.z:.3f} m")
print(f"  Neck height:   {p_neck.z:.3f} m")
print(f"  Head height:   {p_head.z:.3f} m")
print(f"  Spine length (hip->neck): {(p_neck - p_hips).length:.3f} m")

# Also check Mixamo X Bot for comparison
bpy.ops.import_scene.fbx(filepath=r"C:\Users\User\Downloads\X Bot.fbx")
char = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and 'Armature' not in o.name)
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
print(f"\n=== Mixamo X Bot T-pose proportions ===")
for src, tgt in [('Pelvis','mixamorig:Hips'),('Neck','mixamorig:Neck'),('Head','mixamorig:Head')]:
    pb = char.pose.bones.get(tgt)
    if pb:
        w = char.matrix_world @ pb.head
        print(f"  {tgt:30s}  Z(height)={w.z:+.3f} m")
m_hips = char.matrix_world @ char.pose.bones['mixamorig:Hips'].head
m_neck = char.matrix_world @ char.pose.bones['mixamorig:Neck'].head
print(f"  Mixamo spine length (hip->neck): {(m_neck - m_hips).length:.3f} m")
