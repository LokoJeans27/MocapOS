# MocapOS — Installation Guide (licensed models, step by step)

After `setup.bat` finishes, MocapOS has the engine + all public models. The only thing
left is **3 licensed models from Max Planck** (free, but you must register once and
download them yourself — they cannot be redistributed):

| Model | Needed for | Site |
|-------|-----------|------|
| **SMPL-X** | Body (required to render) | https://smpl-x.is.tue.mpg.de/ |
| **SMPL**   | Body (required) | https://smpl.is.tue.mpg.de/ |
| **MANO**   | Hands (optional) | https://mano.is.tue.mpg.de/ |

> Body works with SMPL-X + SMPL. **MANO is only for hands** — without it the body still
> runs and hands are skipped automatically.

There are **two ways** to install each one. The GUI importer is the easy way.

---

## The easy way — GUI importer (recommended)

When you open MocapOS, if any model is missing it opens straight on the **Settings**
page and tells you what's missing. For each model you'll see a card with a
**🌐 Open … site** button and a **📦 Import … zip** button.

For every model the flow is the same:

1. Click **🌐 Open … site**, **register** and **log in**.
2. Download the zip indicated below (the exact button matters).
3. Back in MocapOS, click **📦 Import … zip** and pick the zip you downloaded.
   MocapOS extracts the right files and puts them in the correct folder automatically.
4. The status flips to **[OK]**. Done.

### SMPL-X
- Site: https://smpl-x.is.tue.mpg.de/  → register/login → **Download**
- Click exactly: **"Download SMPL-X v1.1 (NPZ+PKL, 830 MB) — Use this for SMPL-X Python codebase"**
- That gives `models_smplx_v1_1.zip` → **📦 Import SMPL-X zip**.

### SMPL
- Site: https://smpl.is.tue.mpg.de/  → register/login → **Download**
- Click: **"Version 1.1.0 for Python 2.7 (female/male/neutral, 247 MB)"**
- That gives `SMPL_python_v.1.1.0.zip` → **📦 Import SMPL zip** (MocapOS renames the files for you).

### MANO (hands)
- Site: https://mano.is.tue.mpg.de/  → register/login → **Download**
- Click the **first** link: **"Models & Code (mano_v1_2.zip)"**
  *(not the "Extended SMPL+H" / "SMPLH" links — those are something else.)*
- That gives `mano_v1_2.zip` → **📦 Import MANO zip**.
  MocapOS extracts only `MANO_LEFT.pkl` + `MANO_RIGHT.pkl` and ignores the rest.

Once everything is **[OK]**, MocapOS opens normally on the Inference page from then on —
no more setup screen.

---

## The manual way (if you prefer)

Download the same zips, extract them, and copy the files into these folders
(relative to the MocapOS folder):

**SMPL-X** → `inputs/checkpoints/body_models/smplx/`
```
SMPLX_NEUTRAL.npz   (and optionally SMPLX_MALE.npz, SMPLX_FEMALE.npz)
```

**SMPL** → `inputs/checkpoints/body_models/smpl/`  (rename them exactly like this)
```
SMPL_NEUTRAL.pkl    SMPL_MALE.pkl    SMPL_FEMALE.pkl
```

**MANO** → `hamer_lib/_DATA/data/mano/`  (from `mano_v1_2/models/` inside the zip)
```
MANO_LEFT.pkl    MANO_RIGHT.pkl
```

For MANO you can also use the CLI installer (auto-finds the zip in Downloads/Desktop):
```
env\python.exe tools\dev\install_mano.py            (auto-find)
env\python.exe tools\dev\install_mano.py <path-to-mano_v1_2.zip>
```
`setup.bat` also runs this automatically if it finds `mano_v1_2.zip` in your Downloads.

---

## Quick checklist

- [ ] `setup.bat` ran and self-test said **READY**
- [ ] SMPL-X imported → `[OK]`
- [ ] SMPL imported → `[OK]`
- [ ] (optional) MANO imported → `[OK]`  *(only if you want hands)*
- [ ] Run an inference → videos appear in your output folder
