"""Render a character FBX in Workbench for visual comparison."""
import bpy
import sys
from mathutils import Vector

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
fbx_path = argv[0]
out_path = argv[1] if len(argv) > 1 else "C:/Users/User/Desktop/render.png"
frame = int(argv[2]) if len(argv) > 2 else 60

# Clean scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import character
bpy.ops.import_scene.fbx(filepath=fbx_path)
arm = None
meshes = []
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        arm = o
    elif o.type == 'MESH':
        meshes.append(o)

if arm is None:
    print("ERROR: No armature found")
    sys.exit(1)

# Set frame
bpy.context.scene.frame_set(frame)
bpy.context.view_layer.update()

# Compute bounds
verts = []
for m in meshes:
    for v in m.data.vertices:
        verts.append(m.matrix_world @ v.co)

if verts:
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    center = ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2)
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = (0, 0, 1)
    size = 2

# Add camera
cam_dist = max(size * 1.5, 2.0)
bpy.ops.object.camera_add(location=(center[0], center[1] - cam_dist, center[2] + size * 0.3))
cam = bpy.context.active_object
cam.name = "RenderCam"
bpy.context.scene.camera = cam

direction = Vector(center) - cam.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot_quat.to_euler()

# Add lights
bpy.ops.object.light_add(type='SUN', location=(2, -3, 4))
light = bpy.context.active_object
light.data.energy = 3.0
bpy.ops.object.light_add(type='SUN', location=(-2, -3, 4))
light2 = bpy.context.active_object
light2.data.energy = 2.0

# Configure Workbench render
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.filepath = out_path
scene.render.image_settings.file_format = 'PNG'

# Workbench settings for visibility
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'TEXTURE'

# Light background
world = bpy.data.worlds.new(name="LightWorld")
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1.0)
bg.inputs[1].default_value = 1.0
scene.world = world

# Render
bpy.ops.render.render(write_still=True)
print(f"Rendered frame {frame} to {out_path}")
