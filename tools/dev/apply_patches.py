"""
Apply necessary patches to HaMeR for Windows/RTX compatibility.
Run this after installing HaMeR to fix import errors and GPU issues.
"""
import sys
from pathlib import Path

PROJ_DIR = Path(__file__).resolve().parent
HAMER_DIR = PROJ_DIR / "hamer_lib"

patches_applied = 0
patches_skipped = 0


def patch_file(filepath, old_text, new_text, description):
    """Replace old_text with new_text in filepath."""
    global patches_applied, patches_skipped
    path = Path(filepath)
    if not path.exists():
        print(f"  [SKIP] {path.name} - file not found")
        patches_skipped += 1
        return

    content = path.read_text(encoding="utf-8", errors="replace")
    if new_text in content:
        print(f"  [OK]   {description} (already applied)")
        patches_skipped += 1
        return

    if old_text not in content:
        print(f"  [SKIP] {description} (pattern not found)")
        patches_skipped += 1
        return

    content = content.replace(old_text, new_text)
    path.write_text(content, encoding="utf-8")
    patches_applied += 1
    print(f"  [DONE] {description}")


# ── Patch 1: HaMeR renderer import guard ─────────────────────
patch_file(
    HAMER_DIR / "hamer" / "utils" / "__init__.py",
    "from .renderer import Renderer",
    """try:
    from .renderer import Renderer
except Exception:
    Renderer = None""",
    "hamer/utils/__init__.py - renderer import guard"
)

# Also handle SkeletonRenderer and MeshRenderer imports
utils_init = HAMER_DIR / "hamer" / "utils" / "__init__.py"
if utils_init.exists():
    content = utils_init.read_text(encoding="utf-8", errors="replace")
    for cls in ["SkeletonRenderer", "MeshRenderer"]:
        old = f"from .renderer import {cls}"
        new = f"""try:
    from .renderer import {cls}
except Exception:
    {cls} = None"""
        if old in content and new not in content:
            content = content.replace(old, new)
            patches_applied += 1
            print(f"  [DONE] {cls} import guard")
    utils_init.write_text(content, encoding="utf-8")

# ── Patch 2: HaMeR model renderer None check ─────────────────
patch_file(
    HAMER_DIR / "hamer" / "models" / "hamer.py",
    "if init_renderer:",
    "if init_renderer and SkeletonRenderer is not None and MeshRenderer is not None:",
    "hamer/models/hamer.py - renderer None guard"
)

# ── Patch 3: HaMeR CACHE_DIR absolute path ───────────────────
configs_init = HAMER_DIR / "hamer" / "configs" / "__init__.py"
if configs_init.exists():
    content = configs_init.read_text(encoding="utf-8", errors="replace")
    if 'CACHE_DIR_HAMER' in content:
        # Check if it uses a relative path
        if "\"_DATA\"" in content or "'_DATA'" in content:
            hamer_data = str(HAMER_DIR / "_DATA").replace("\\", "/")
            content = content.replace(
                'CACHE_DIR_HAMER = "_DATA"',
                f'CACHE_DIR_HAMER = "{hamer_data}"'
            )
            content = content.replace(
                "CACHE_DIR_HAMER = '_DATA'",
                f"CACHE_DIR_HAMER = '{hamer_data}'"
            )
            configs_init.write_text(content, encoding="utf-8")
            patches_applied += 1
            print("  [DONE] hamer/configs/__init__.py - absolute CACHE_DIR")
        else:
            print("  [OK]   CACHE_DIR already absolute")
    else:
        patches_skipped += 1

# ── Patch 4: Suppress ViTDetDataset debug print ──────────────
patch_file(
    HAMER_DIR / "hamer" / "datasets" / "vitdet_dataset.py",
    "print(f'{downsampling_factor=}')",
    "# print(f'{downsampling_factor=}')",
    "vitdet_dataset.py - suppress debug print"
)

print(f"\nPatches: {patches_applied} applied, {patches_skipped} skipped")
