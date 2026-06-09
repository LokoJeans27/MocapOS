import bpy, math, sys
from mathutils import Vector, Matrix

p = "C:/Users/User/Downloads/T-Pose (1).fbx"
bpy.ops.import_scene.fbx(filepath=p)
arm = [o for o in bpy.context.selected_objects if o.type=='ARMATURE'][0]
arm.name = 'Character'

TEMPLATE_PATH = r"C:/Users/User/Downloads/X Bot.fbx"
bpy.ops.import_scene.fbx(filepath=TEMPLATE_PATH)
template = [o for o in bpy.data.objects if o.type=='ARMATURE' and o!=arm][0]

bone_map = {
    'mixamorig:Hips':'mixamorig:Hips', 'mixamorig:Spine':'mixamorig:Spine',
    'mixamorig:Spine1':'mixamorig:Spine1', 'mixamorig:Spine2':'mixamorig:Spine2',
    'mixamorig:LeftShoulder':'mixamorig:LeftShoulder',
    'mixamorig:LeftArm':'mixamorig:LeftArm',
    'mixamorig:LeftForeArm':'mixamorig:LeftForeArm',
    'mixamorig:LeftHand':'mixamorig:LeftHand',
    'mixamorig:RightShoulder':'mixamorig:RightShoulder',
    'mixamorig:RightArm':'mixamorig:RightArm',
    'mixamorig:RightForeArm':'mixamorig:RightForeArm',
    'mixamorig:RightHand':'mixamorig:RightHand',
    'mixamorig:LeftUpLeg':'mixamorig:LeftUpLeg',
    'mixamorig:LeftLeg':'mixamorig:LeftLeg',
    'mixamorig:LeftFoot':'mixamorig:LeftFoot',
    'mixamorig:RightUpLeg':'mixamorig:RightUpLeg',
    'mixamorig:RightLeg':'mixamorig:RightLeg',
    'mixamorig:RightFoot':'mixamorig:RightFoot',
    'mixamorig:Head':'mixamorig:Head',
    'mixamorig:Neck':'mixamorig:Neck',
}

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')

for b in arm.data.edit_bones:
    tname = bone_map.get(b.name)
    if not tname:
        continue
    template_b = template.data.edit_bones.get(tname)
    if not template_b:
        continue
    
    target_dir = template_b.tail - template_b.head
    current_dir = b.tail - b.head
    
    # Direction alignment
    axis = current_dir.cross(target_dir)
    if axis.length > 1e-6:
        angle = math.atan2(axis.length, current_dir.dot(target_dir))
        axis.normalize()
        rot = Matrix.Rotation(angle, 3, axis)
        b.tail = b.head + rot @ (b.tail - b.head)
        for child in b.children:
            if child.use_connect:
                child.head = b.tail
    
    # NEW roll calculation
    x_axis_ref = template_b.x_axis.normalized()
    y_axis = (b.tail - b.head).normalized()
    
    # Save old roll, set to 0, read x_axis at zero roll
    old_roll = b.roll
    b.roll = 0.0
    x_axis_zero = b.x_axis.normalized()
    
    # Calculate roll needed to align x_axis_zero to x_axis_ref around y_axis
    # Project x_axis_ref onto the plane perpendicular to y_axis
    x_proj = x_axis_ref - x_axis_ref.dot(y_axis) * y_axis
    if x_proj.length > 1e-6:
        x_proj.normalize()
        # Angle from x_axis_zero to x_proj around y_axis
        dot_x = x_proj.dot(x_axis_zero)
        cross_y = x_proj.cross(x_axis_zero).dot(y_axis)
        target_roll = math.atan2(cross_y, dot_x)
    else:
        target_roll = 0.0
    
    b.roll = target_roll
    
    if b.name in ['mixamorig:LeftUpLeg', 'mixamorig:Hips', 'mixamorig:LeftLeg', 'mixamorig:LeftArm']:
        print(f"\n=== {b.name} ===")
        print(f"  x_axis_ref={tuple(x_axis_ref)}")
        print(f"  x_axis_zero={tuple(x_axis_zero)}")
        print(f"  y_axis={tuple(y_axis)}")
        print(f"  target_roll={target_roll:.6f} (old={old_roll:.6f})")

bpy.ops.object.mode_set(mode='OBJECT')

# Check result
for name in ['mixamorig:LeftUpLeg', 'mixamorig:Hips', 'mixamorig:LeftLeg', 'mixamorig:LeftArm']:
    b = arm.data.bones.get(name)
    if b:
        m = b.matrix_local.to_3x3()
        vals = [round(float(m[r][c]),3) for r in range(3) for c in range(3)]
        print(f"\nFINAL {name}: {tuple(vals)}")
