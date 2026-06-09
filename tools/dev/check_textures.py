import bpy, sys
bpy.ops.import_scene.fbx(filepath=sys.argv[-1])
for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        print(f"Object: {obj.name}")
        for slot in obj.material_slots:
            mat = slot.material
            if mat:
                print(f"  Material: {mat.name}")
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == 'TEX_IMAGE' and node.image:
                            print(f"    Texture: {node.image.name} ({node.image.filepath})")
                        elif node.type == 'TEX_IMAGE':
                            print(f"    Texture node: {node.name} (NO IMAGE)")
                else:
                    print(f"    (No nodes - basic material)")
                    if mat.texture_slots:
                        for i, ts in enumerate(mat.texture_slots):
                            if ts and ts.texture:
                                print(f"    Texture slot {i}: {ts.texture.name}")
