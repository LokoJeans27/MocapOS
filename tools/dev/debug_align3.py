import bpy, math, sys
from mathutils import Vector, Matrix

p = "C:/Users/User/Downloads/T-Pose (1).fbx"
bpy.ops.import_scene.fbx(filepath=p)
arm = [o for o in bpy.context.selected_objects if o.type=='ARMATURE'][0]
arm.name = 'Character'

TEMPLATE_PATH = r"C:/Users/User/Downloads/X Bot.fbx"
bpy.ops.import_scene.fbx(filepath=TEMPLATE_PATH)
template = [o for o in bpy.data.objects if o.type=='ARMATURE' and o!=arm][0]

align_bones = [
    "mixamorig:Hips",
    "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2",
    "mixamorig:LeftShoulder", "mixamorig:LeftArm", "mixamorig:LeftForeArm", "mixamorig:LeftHand",
    "mixamorig:RightShoulder", "mixamorig:RightArm", "mixamorig:RightForeArm", "mixamorig:RightHand",
    "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
    "mixamorig:RightUpLeg", "mixamorig:RightLeg", "mixamorig:RightFoot",
    "mixamorig:Neck", "mixamorig:Head",
]

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')

# Process in topological order
def topo_order(names, edit_bones):
    ordered = []
    visited = set()
    def visit(name):
        if name in visited:
            return
        b = edit_bones.get(name)
        if b and b.parent and b.parent.name in names:
            visit(b.parent.name)
        visited.add(name)
        ordered.append(name)
    for name in names:
        visit(name)
    return ordered

ordered = topo_order(align_bones, arm.data.edit_bones)
print("Order:", ordered)

for bone_name in ordered:
    char_edit = arm.data.edit_bones.get(bone_name)
    tmpl_edit = template.data.edit_bones.get(bone_name)
    if not char_edit or not tmpl_edit:
        continue
    
    # 1) Align direction
    tmpl_dir = (tmpl_edit.tail - tmpl_edit.head).normalized()
    current_length = (char_edit.tail - char_edit.head).length
    char_edit.tail = char_edit.head + tmpl_dir * current_length
    
    # 2) Align roll using matrix columns (as in retarget_blender.py)
    A_char = char_edit.matrix.to_3x3()
    A_tmpl = tmpl_edit.matrix.to_3x3()
    y = A_char.col[1]
    x_char = A_char.col[0] - A_char.col[0].project(y)
    x_tmpl = A_tmpl.col[0] - A_tmpl.col[0].project(y)
    if x_char.length > 1e-6 and x_tmpl.length > 1e-6:
        x_char.normalize()
        x_tmpl.normalize()
        cos_a = x_char.dot(x_tmpl)
        sin_a = x_char.cross(x_tmpl).dot(y)
        roll_delta = math.atan2(sin_a, cos_a)
        old_roll = char_edit.roll
        char_edit.roll += roll_delta
        if bone_name in ['mixamorig:LeftUpLeg', 'mixamorig:LeftArm']:
            print(f"{bone_name}: roll_delta={roll_delta:.6f} old={old_roll:.6f} new={char_edit.roll:.6f}")

bpy.ops.object.mode_set(mode='OBJECT')

# Check result
for name in ['mixamorig:LeftUpLeg', 'mixamorig:LeftLeg', 'mixamorig:LeftArm', 'mixamorig:Hips']:
    b = arm.data.bones.get(name)
    if b:
        m = b.matrix_local.to_3x3()
        vals = [round(float(m[r][c]),3) for r in range(3) for c in range(3)]
        print(f"FINAL {name}: {tuple(vals)}")
