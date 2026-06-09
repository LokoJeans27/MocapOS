"""
Set up test.blend with camera + ground + lights, import REF_mixamo.fbx,
render specified frames as PNG via Eevee.

Usage:
    blender --background test.blend --python render_test.py -- \
        --fbx out.fbx --frames 1,60,130,200 --out_dir /tmp/render
"""
import bpy
import sys
import os
import math
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--frames", default="1,60,130,200")
    p.add_argument("--out_dir", required=True)
    p.add_argument("--cam_az", type=float, default=-30.0,
                   help="camera azimuth deg around target (0=front along -Y)")
    p.add_argument("--cam_el", type=float, default=15.0, help="elevation deg")
    p.add_argument("--cam_dist", type=float, default=4.5)
    p.add_argument("--cam_target_z", type=float, default=1.0)
    return p.parse_args(argv)


def clean_animation_objects():
    # Remove any pre-existing armatures or imported FBX leftovers (keep camera/lights)
    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'MESH'):
            bpy.data.objects.remove(o, do_unlink=True)


def import_fbx(path):
    bpy.ops.import_scene.fbx(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    return arms[0] if arms else None


def setup_camera(az_deg, el_deg, dist, target_z):
    cam = bpy.data.objects.get("Camera")
    if cam is None:
        cam_data = bpy.data.cameras.new("Camera")
        cam_data.lens = 24
        cam = bpy.data.objects.new("Camera", cam_data)
        bpy.context.scene.collection.objects.link(cam)
    else:
        cam.data.lens = 24

    az = math.radians(az_deg)
    el = math.radians(el_deg)
    x = dist * math.cos(el) * math.sin(az)
    y = -dist * math.cos(el) * math.cos(az)
    z = target_z + dist * math.sin(el)
    cam.location = (x, y, z)

    target = Vector((0.0, 0.0, target_z))
    direction = target - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = cam
    return cam


def setup_lights():
    # Sun
    if "KeySun" not in bpy.data.objects:
        d = bpy.data.lights.new("KeySun", type='SUN')
        d.energy = 3.0
        o = bpy.data.objects.new("KeySun", d)
        bpy.context.scene.collection.objects.link(o)
        o.rotation_euler = (math.radians(45), math.radians(20), 0)
    # World ambient
    w = bpy.context.scene.world
    if w is None:
        w = bpy.data.worlds.new("World")
        bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.85, 0.85, 0.85, 1.0)
        bg.inputs[1].default_value = 1.0


def setup_ground():
    if "Ground" not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
        plane = bpy.context.active_object
        plane.name = "Ground"
        # Checker material
        mat = bpy.data.materials.new("GroundMat")
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        chk = nt.nodes.new("ShaderNodeTexChecker")
        chk.inputs[3].default_value = 4.0
        chk.inputs[1].default_value = (0.55, 0.6, 0.6, 1.0)
        chk.inputs[2].default_value = (0.7, 0.75, 0.75, 1.0)
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(chk.outputs[0], bsdf.inputs[0])
        nt.links.new(bsdf.outputs[0], out.inputs[0])
        plane.data.materials.append(mat)


def main():
    args = parse_args()

    clean_animation_objects()
    arm = import_fbx(args.fbx)
    if arm is None:
        print("ERROR: no armature in FBX")
        sys.exit(1)
    print(f"Imported: {arm.name} ({len(arm.data.bones)} bones)")

    setup_camera(args.cam_az, args.cam_el, args.cam_dist, args.cam_target_z)
    setup_lights()
    setup_ground()

    s = bpy.context.scene
    # Eevee
    s.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'EEVEE_NEXT') else 'BLENDER_EEVEE'
    try:
        s.render.engine = 'BLENDER_EEVEE_NEXT'
    except Exception:
        s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x = 960
    s.render.resolution_y = 540
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'

    os.makedirs(args.out_dir, exist_ok=True)
    frames = [int(x) for x in args.frames.split(",") if x.strip()]
    for f in frames:
        s.frame_set(f)
        s.render.filepath = os.path.join(args.out_dir, f"render_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered frame {f} -> {s.render.filepath}")

    print("DONE")


if __name__ == "__main__":
    main()
