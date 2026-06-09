with open(r'C:\Users\User\Documents\MocapOS\gvhmr_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace literal tooltip texts with self._t() calls
replacements = [
    ('Tooltip(sw_static, "Assumes the camera is not moving.\nSkips visual odometry estimation.")',
     'Tooltip(sw_static, self._t("static_cam_tip"))'),
    ('Tooltip(sw_dpvo, "Uses DPVO for visual odometry\ninstead of the faster SimpleVO.")',
     'Tooltip(sw_dpvo, self._t("use_dpvo_tip"))'),
    ('Tooltip(sw_verbose, "Saves intermediate results (images, debug data)\nfor troubleshooting.")',
     'Tooltip(sw_verbose, self._t("verbose_tip"))'),
    ('Tooltip(sw_hands, "Enables HaMeR hand/finger tracking\non top of body motion capture.")',
     'Tooltip(sw_hands, self._t("hands_tip"))'),
    ('Tooltip(sw_focal, "Manually set the camera focal length in mm\nfor more accurate 3D reconstruction.")',
     'Tooltip(sw_focal, self._t("focal_tip"))'),
    ('Tooltip(ent_focal, "Focal length in millimeters. Common values:\n24mm (wide), 50mm (standard), 85mm (tele).")',
     'Tooltip(ent_focal, self._t("focal_entry_tip"))'),
    ('Tooltip(ent_edir, "Folder containing hmr4d_results.pt from Inference.\nUsually: outputs/results/VIDEO_NAME")',
     'Tooltip(ent_edir, self._t("results_tip"))'),
    ('Tooltip(ent_eout, "Path for the exported BVH file.\nLeave empty for auto-naming.")',
     'Tooltip(ent_eout, self._t("output_tip"))'),
    ('Tooltip(sw_body, "Export only 22 body joints.\nSkips hand and face bones for simpler rigs.")',
     'Tooltip(sw_body, self._t("body_only_tip"))'),
    ('Tooltip(ent_efps, "Frame rate of the exported animation.\nDefault is 30 fps.")',
     'Tooltip(ent_efps, self._t("fps_tip"))'),
    ('Tooltip(ent_escale, "Unit scale for the exported BVH.\n100 = centimeters, 1 = meters.")',
     'Tooltip(ent_escale, self._t("scale_tip"))'),
    ('Tooltip(ent_results, "Folder containing hmr4d_results.pt\nfrom a previous Inference run.")',
     'Tooltip(ent_results, self._t("results_folder_tip"))'),
    ('Tooltip(ent_char, "Your target character with Mixamo skeleton in A-Pose.\nT-Pose will NOT work correctly.")',
     'Tooltip(ent_char, self._t("char_tip"))'),
    ('Tooltip(ent_blend, "Path to Blender.exe for background processing.\nRequired for skeleton retargeting.")',
     'Tooltip(ent_blend, self._t("blender_tip"))'),
    ('Tooltip(cb_fmt, "3D file format for the exported animated character.\nFBX is the most compatible.")',
     'Tooltip(cb_fmt, self._t("format_tip"))'),
    ('Tooltip(ent_out, "Where to save the final animated character file.\nExtension updates automatically based on format.")',
     'Tooltip(ent_out, self._t("out_path_tip"))'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f'Replaced: {old[:50]}...')
    else:
        print(f'NOT FOUND: {old[:50]}...')

with open(r'C:\Users\User\Documents\MocapOS\gvhmr_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
