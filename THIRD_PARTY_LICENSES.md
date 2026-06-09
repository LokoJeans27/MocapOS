# Third-Party Components & Licenses

MocapOS is a **derivative work of GVHMR** that bundles several research models and
libraries. **Each one keeps its own license.** This file lists them so that anyone
using MocapOS knows the terms.

> ⚠️ **MocapOS as a whole is NON-COMMERCIAL.** Several core components below
> (GVHMR, SMPL/SMPL-X/MANO, and YOLOv8 under AGPL) forbid or restrict commercial
> use. You may use MocapOS for research, learning, personal and non-profit work.
> **You may not sell it, offer it as a paid product/service, or use it inside a
> commercial product** without obtaining the proper commercial licenses from each
> rights holder (see the contacts below).

| Component | Role | License | Commercial use |
|-----------|------|---------|----------------|
| **GVHMR** (zju3dv) | Body motion recovery (core engine) | Custom, **non-commercial** | ❌ No — contact `xwzhou@zju.edu.cn` |
| **SMPL / SMPL-X / MANO** (Max Planck) | Body & hand mesh models | Academic license, **non-commercial** | ❌ No — contact `sales@meshcapade.com` |
| **HaMeR** (geopavlakos) | Hand mesh recovery | MIT (but **depends on MANO**) | ⚠️ Code MIT, model bound by MANO |
| **YOLOv8 / Ultralytics** | Person detection | **AGPL-3.0** (copyleft) | ⚠️ Requires open-sourcing the whole work under AGPL **or** an Ultralytics Enterprise License |
| **ViTPose / MMPose / MMCV** | 2D keypoints | Apache-2.0 | ✅ Yes |
| **Detectron2** (Meta) | Detection backbone | Apache-2.0 | ✅ Yes |
| **PyTorch3D** (Meta) | 3D ops | BSD-3-Clause | ✅ Yes |
| **DPVO** (princeton-vl) | Visual odometry | MIT | ✅ Yes |

## Model weights are NOT redistributed in this repository

- **SMPL / SMPL-X / MANO** must be downloaded by each user from the official sites,
  after accepting the Max Planck license:
  - SMPL-X: <https://smpl-x.is.tue.mpg.de/>
  - SMPL: <https://smpl.is.tue.mpg.de/>
- Tracking model weights are fetched at install time from their public sources by
  `tools/dev/fetch_models.py`.
- The portable Python environments are hosted on Hugging Face and downloaded by
  `setup.bat`. They contain the libraries above under their respective licenses.

## License references

- GVHMR: <https://github.com/zju3dv/GVHMR/blob/main/LICENSE> (preserved here as `LICENSE`)
- SMPL: <https://smpl.is.tue.mpg.de/modellicense.html>
- SMPL-X: <https://smpl-x.is.tue.mpg.de/modellicense.html>
- HaMeR: <https://github.com/geopavlakos/hamer>
- Ultralytics (AGPL/Enterprise): <https://www.ultralytics.com/license>
- DPVO: <https://github.com/princeton-vl/DPVO/blob/main/LICENSE>

If you believe any attribution here is incomplete or incorrect, please open an issue.
