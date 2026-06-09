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

template_mw = template.matrix_world
char_mw = arm.matrix_world

for b in arm.data.edit_bones:
    tname = bone_map.get(b.name)
    if not tname:
        continue
    template_b = template.data.edit_bones.get(tname)
    if not template_b:
        continue
    
    target_dir = template_b.tail - template_b.head
    current_dir = b.tail - b.head
    
    if b.name in ['mixamorig:LeftUpLeg', 'mixamorig:Hips']:
        print(f"\n=== {b.name} ===")
        print(f"  BEFORE: head={tuple(b.head)} tail={tuple(b.tail)}")
        print(f"  target_dir={tuple(target_dir)} current_dir={tuple(current_dir)}")
    
    axis = current_dir.cross(target_dir)
    if axis.length > 1e-6:
        angle = math.atan2(axis.length, current_dir.dot(target_dir))
        axis.normalize()
        rot = Matrix.Rotation(angle, 3, axis)
        b.tail = b.head + rot @ (b.tail - b.head)
        for child in b.children:
            if child.use_connect:
                child.head = b.tail
        if b.name in ['mixamorig:LeftUpLeg', 'mixamorig:Hips']:
            print(f"  AFTER direction: head={tuple(b.head)} tail={tuple(b.tail)}")
    
    # roll
    x_axis_ref = template_b.x_axis.normalized()
    x_axis_current = b.x_axis.normalized()
    y_axis = (b.tail - b.head).normalized()
    x_axis = b.x_axis.normalized()
    target_roll = math.atan2(x_axis_ref.dot(y_axis), x_axis_ref.dot(x_axis))
    old_roll = b.roll
    b.roll = target_roll
    
    if b.name in ['mixamorig:LeftUpLeg', 'mixamorig:Hips']:
        print(f"  x_axis_ref={tuple(x_axis_ref)} x_axis_cur={tuple(x_axis_current)}")
        print(f"  y_axis={tuple(y_axis)} x_axis_dot={x_axis_ref.dot(x_axis_current):.6f} y_dot={x_axis_ref.dot(y_axis):.6f}")
        print(f"  roll: old={old_roll:.6f} new={b.roll:.6f}")

bpy.ops.object.mode_set(mode='OBJECT')

# Check result
for name in ['mixamorig:LeftUpLeg', 'mixamorig:Hips']:
    b = arm.data.bones.get(name)
    if b:
        m = b.matrix_local.to_3x3()
        vals = [round(float(m[r][c]),3) for r in range(3) for c in range(3)]
        print(f"\nFINAL {name}: {tuple(vals)}")
        print(f"  head={tuple(b.head_local)} tail={tuple(b.tail_local)}")
