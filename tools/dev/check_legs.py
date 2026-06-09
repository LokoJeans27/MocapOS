import bpy, sys
p1, p2 = sys.argv[-2], sys.argv[-1]

for p in [p1, p2]:
    if p.endswith('.fbx'):
        bpy.ops.import_scene.fbx(filepath=p)
    print(f"\n=== {p.split('/')[-1]} ===")
    arm = [o for o in bpy.data.objects if o.type=='ARMATURE'][0]
    for name in ['mixamorig:LeftUpLeg', 'mixamorig:LeftLeg', 'mixamorig:RightUpLeg', 'mixamorig:RightLeg', 'mixamorig:Hips']:
        b = arm.data.bones.get(name)
        if b:
            m3 = b.matrix_local.to_3x3()
            # flattened row-major
            vals = []
            for row in range(3):
                for col in range(3):
                    vals.append(round(float(m3[row][col]), 3))
            m = tuple(vals)
            h = tuple(round(float(v),3) for v in b.head_local)
            t = tuple(round(float(v),3) for v in b.tail_local)
            print(f"{name}: {m}")
            print(f"  head={h}  tail={t}")
    # cleanup
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
