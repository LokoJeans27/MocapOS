"""
Runs INSIDE Blender (headless):

    blender --background --python tools/export/export_mesh_blender.py -- \
        --npz  cache.npz  --fbx out.fbx  --abc out.abc

Reads a mesh-cache .npz produced by tools/export/export_mesh.py and writes:
  * a RIGGED SMPL character (24-bone armature + skinned mesh + baked animation) -> FBX
  * an EXACT vertex-cache of the same body (no rig)                              -> Alembic (.abc)

The .npz holds (native SMPL Y-up, meters):
    faces        (F,3) int
    weights      (V,24) float   skinning weights
    parents      (24,)  int     kintree, parents[0] = -1
    joint_names  (24,)  str
    rest_joints  (24,3) float   zero-pose joint positions (bone heads)
    rest_verts   (V,3)  float   un-posed mesh
    pose         (L,24,3) float local axis-angle per joint per frame
    transl       (L,3)  float   root translation per frame
    verts        (L,V,3) float  exact deformed mesh per frame (the previewed body)
    fps          (1,)   float

SMPL is Y-up; Blender is Z-up. We keep all data in native Y-up and stand the
objects upright with a +90deg X object rotation, baked on export.
"""

import sys
import math

import numpy as np

try:
    import bpy
    from mathutils import Vector, Quaternion, Euler
except ImportError:
    print("ERROR: this script must be run inside Blender (blender --background --python ...).")
    sys.exit(1)


# Y-up (SMPL) -> Z-up (Blender), applied as an object-level rotation and baked on export
STAND_UP = Euler((math.radians(90.0), 0.0, 0.0), "XYZ")


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--npz", required=True)
    p.add_argument("--fbx", required=True)
    p.add_argument("--abc", required=True)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.armatures, bpy.data.objects):
        for b in list(block):
            try:
                block.remove(b)
            except Exception:
                pass


def aa_to_quat(aa):
    """axis-angle (3,) -> mathutils.Quaternion (relative to identity rest)."""
    angle = float(np.linalg.norm(aa))
    if angle < 1e-8:
        return Quaternion((1.0, 0.0, 0.0, 0.0))
    axis = Vector((float(aa[0]), float(aa[1]), float(aa[2]))) / angle
    return Quaternion(axis, angle)


def build_armature(rest_joints, parents, names):
    """Armature whose bones are all world-axis-aligned (identity rest orientation),
    so SMPL local axis-angle maps directly to pose_bone.rotation_quaternion."""
    arm_data = bpy.data.armatures.new("SMPL_Armature")
    arm_obj = bpy.data.objects.new("SMPL_Armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    ebones = []
    for j, name in enumerate(names):
        b = arm_data.edit_bones.new(name)
        head = Vector((float(rest_joints[j][0]), float(rest_joints[j][1]), float(rest_joints[j][2])))
        b.head = head
        b.tail = head + Vector((0.0, 0.05, 0.0))   # +Y, roll 0 -> identity bone matrix
        b.roll = 0.0
        ebones.append(b)

    for j in range(len(names)):
        p = int(parents[j])
        if p >= 0:
            ebones[j].parent = ebones[p]
            ebones[j].use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def build_skinned_mesh(rest_verts, faces, weights, names, arm_obj):
    """Mesh at rest pose, bound to the armature via per-bone vertex groups."""
    mesh = bpy.data.meshes.new("SMPL_Mesh")
    verts = [tuple(map(float, v)) for v in rest_verts]
    polys = [tuple(map(int, f)) for f in faces]
    mesh.from_pydata(verts, [], polys)
    mesh.update()

    obj = bpy.data.objects.new("SMPL_Mesh", mesh)
    bpy.context.collection.objects.link(obj)

    # vertex groups + weights (one group per bone)
    groups = [obj.vertex_groups.new(name=n) for n in names]
    for j, vg in enumerate(groups):
        wj = weights[:, j]
        for vi in np.nonzero(wj > 1e-6)[0]:
            vg.add([int(vi)], float(wj[vi]), "REPLACE")

    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm_obj
    mod.use_vertex_groups = True
    obj.parent = arm_obj
    return obj


def animate(arm_obj, pose, transl, fps):
    L = pose.shape[0]
    scene = bpy.context.scene
    scene.render.fps = int(round(fps))
    scene.frame_start = 0
    scene.frame_end = L - 1

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")
    pbones = arm_obj.pose.bones
    for pb in pbones:
        pb.rotation_mode = "QUATERNION"

    nb = pose.shape[1]
    for f in range(L):
        scene.frame_set(f)
        for j in range(nb):
            pb = pbones[j]
            pb.rotation_quaternion = aa_to_quat(pose[f, j])
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if j == 0:  # root translation (identity rest -> world-aligned offset)
                pb.location = Vector((float(transl[f, 0]), float(transl[f, 1]), float(transl[f, 2])))
                pb.keyframe_insert("location", frame=f)

    bpy.ops.object.mode_set(mode="OBJECT")


def export_fbx(arm_obj, mesh_obj, path):
    arm_obj.rotation_euler = STAND_UP
    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        apply_unit_scale=True,
        bake_space_transform=True,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        axis_forward="-Z",
        axis_up="Y",
        object_types={"ARMATURE", "MESH"},
    )
    print(f"[Blender] FBX written: {path}")


def export_alembic(verts, faces, fps, path):
    """Exact vertex cache: one mesh deformed per frame via keyframed shape keys
    (the Alembic exporter evaluates these), then exported to Alembic (no rig)."""
    L = verts.shape[0]
    # Cache is pure positions (no rig), so bake Y-up -> Z-up straight into the
    # vertices: (x, y, z) -> (x, -z, y). Avoids relying on object transforms,
    # which the Alembic exporter does not bake reliably.
    v = verts.astype(np.float64)
    verts = np.stack([v[..., 0], -v[..., 2], v[..., 1]], axis=-1)

    mesh = bpy.data.meshes.new("SMPL_Cache")
    mesh.from_pydata([tuple(map(float, vv)) for vv in verts[0]], [], [tuple(map(int, f)) for f in faces])
    mesh.update()
    obj = bpy.data.objects.new("SMPL_Cache", mesh)
    bpy.context.collection.objects.link(obj)

    bpy.context.view_layer.objects.active = obj

    # Basis + one shape key per frame; only frame f's key is active at frame f.
    obj.shape_key_add(name="Basis", from_mix=False)
    keys = []
    for f in range(L):
        sk = obj.shape_key_add(name=f"f{f:05d}", from_mix=False)
        sk.data.foreach_set("co", verts[f].astype(np.float64).ravel())
        sk.value = 0.0
        keys.append(sk)

    # Each key is 1.0 only at its own frame and 0.0 at the neighbours. At every
    # integer frame exactly one key is active, so Alembic (sampled at integer
    # frames) gets the exact vertices regardless of fcurve interpolation.
    for f, sk in enumerate(keys):
        if f > 0:
            sk.value = 0.0; sk.keyframe_insert("value", frame=f - 1)
        sk.value = 1.0; sk.keyframe_insert("value", frame=f)
        if f < L - 1:
            sk.value = 0.0; sk.keyframe_insert("value", frame=f + 1)

    scene = bpy.context.scene
    scene.render.fps = int(round(fps))
    scene.frame_start = 0
    scene.frame_end = L - 1
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.alembic_export(
        filepath=path,
        selected=True,
        start=0,
        end=L - 1,
        flatten=False,
        face_sets=False,
        uvs=False,
        normals=False,         # recomputed by the DCC; keeps the cache much smaller
        apply_subdiv=False,
    )
    print(f"[Blender] Alembic written: {path}")


def main():
    args = parse_args()
    data = np.load(args.npz, allow_pickle=True)
    faces = data["faces"]
    weights = data["weights"]
    parents = data["parents"]
    names = [str(x) for x in data["joint_names"]]
    rest_joints = data["rest_joints"]
    rest_verts = data["rest_verts"]
    pose = data["pose"]
    transl = data["transl"]
    verts = data["verts"]
    fps = float(data["fps"][0])

    clear_scene()

    # --- Rigged FBX ---
    arm = build_armature(rest_joints, parents, names)
    mesh_obj = build_skinned_mesh(rest_verts, faces, weights, names, arm)
    animate(arm, pose, transl, fps)
    export_fbx(arm, mesh_obj, args.fbx)

    # --- Exact Alembic vertex cache ---
    export_alembic(verts, faces, fps, args.abc)

    print("[Blender] Done.")


if __name__ == "__main__":
    main()
