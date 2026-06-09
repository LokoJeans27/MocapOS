import bpy
p = bpy.ops.export_scene.fbx.get_rna_type().properties['path_mode']
print(f"path_mode enum items:")
for item in p.enum_items:
    print(f"  {item.identifier}: {item.name} - {item.description}")
print(f"\nembed_textures: {bpy.ops.export_scene.fbx.get_rna_type().properties['embed_textures'].description}")
