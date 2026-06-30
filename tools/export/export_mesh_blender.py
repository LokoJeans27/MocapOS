"""
Runs INSIDE Blender (headless):

    blender --background --python tools/export/export_mesh_blender.py -- \
        --npz cache.npz  --abc out.abc

Reads a mesh-cache .npz produced by tools/export/export_mesh.py and writes an
exact per-frame vertex cache (the body you see in the MocapOS preview) to
Alembic (.abc). No rig: the .abc carries the deforming mesh exactly.

The .npz holds (native SMPL/SMPL-X Y-up, metres):
    faces  (F,3) int
    verts  (L,V,3) float   exact deformed mesh per frame (the previewed body)
    fps    (1,)   float
(other fields may be present but are unused here).
"""

import sys

import numpy as np

try:
    import bpy
except ImportError:
    print("ERROR: this script must be run inside Blender (blender --background --python ...).")
    sys.exit(1)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--npz", required=True)
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


def export_alembic(verts, faces, fps, path):
    """Exact vertex cache: one mesh deformed per frame via keyframed shape keys
    (the Alembic exporter evaluates these), then exported to Alembic."""
    L = verts.shape[0]
    # Bake Y-up -> Z-up straight into the vertices: (x, y, z) -> (x, -z, y).
    # Avoids relying on object transforms, which the Alembic exporter does not
    # bake reliably.
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
    verts = data["verts"]
    fps = float(data["fps"][0])

    clear_scene()
    export_alembic(verts, faces, fps, args.abc)
    print("[Blender] Done.")


if __name__ == "__main__":
    main()
