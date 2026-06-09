"""Make a freshly unpacked portable env import the app's source packages.

The shipped env was built with editable installs (`pip install -e .`) whose
PEP 660 finders hardcode the BUILD machine's absolute paths
(C:\\Users\\...\\MocapOS\\hmr4d, ...\\hamer_lib\\hamer). Those break on any other
machine / path. We remove them and drop a single relocation-proof `.pth` that
adds the app root (one level above the env) and `hamer_lib` to sys.path at
runtime, derived from sys.prefix. This survives the whole MocapOS folder being
moved or renamed.

Run once by setup.bat with the bundled env python:
    env\\python.exe tools\\dev\\fix_env_paths.py
"""

import pathlib
import site
import sys


def site_packages_dir() -> pathlib.Path:
    for d in site.getsitepackages():
        if d.lower().replace("\\", "/").endswith("site-packages"):
            return pathlib.Path(d)
    # Fallback: <prefix>/Lib/site-packages
    return pathlib.Path(sys.prefix) / "Lib" / "site-packages"


def main():
    sp = site_packages_dir()
    if not sp.exists():
        print(f"ERROR: site-packages not found at {sp}", file=sys.stderr)
        sys.exit(1)

    removed = 0
    for pattern in ("__editable__*.pth", "__editable___*_finder.py"):
        for f in sp.glob(pattern):
            f.unlink()
            removed += 1
            print(f"  removed {f.name}")

    pth = sp / "mocapos_paths.pth"
    pth.write_text(
        "import os, sys; _a=os.path.dirname(sys.prefix); "
        "sys.path.insert(0, _a); "
        "sys.path.insert(0, os.path.join(_a, 'hamer_lib'))\n",
        encoding="utf-8",
    )
    print(f"  wrote {pth.name} (removed {removed} stale editable artifact(s))")

    # Sanity check: the two source packages must now resolve.
    app = pathlib.Path(sys.prefix).parent
    ok = (app / "hmr4d" / "__init__.py").exists() and \
         (app / "hamer_lib" / "hamer" / "__init__.py").exists()
    if not ok:
        print(f"  WARNING: expected source at {app}\\hmr4d and "
              f"{app}\\hamer_lib\\hamer not found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
