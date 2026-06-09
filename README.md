# MocapOS — Full Body + Hands Motion Capture

**MocapOS** turns a single video into 3D body **and hand** motion capture, with a
simple desktop GUI and a **portable installer that compiles nothing** on your
machine. It builds on [GVHMR](https://github.com/zju3dv/GVHMR) (body) and
[HaMeR](https://github.com/geopavlakos/hamer) (hands).

> ⚠️ **Non-commercial project.** MocapOS is free for research, learning, and
> personal/non-profit use. It bundles components that **forbid commercial use**
> (GVHMR, SMPL/SMPL-X/MANO) or require special licensing (YOLOv8/AGPL). See
> [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) before doing anything
> commercial. The MocapOS-authored code is under
> [PolyForm Noncommercial 1.0.0](LICENSE-MocapOS.md).

---

## Install (Windows, NVIDIA GPU)

No Build Tools, no compiling, no `conda activate`. A pre-built environment is
downloaded automatically and matched to your GPU.

1. **Clone** this repo (it is small — the heavy files are not here):
   ```bash
   git clone https://github.com/LokoJeans27/MocapOS.git
   cd MocapOS
   ```
2. **Run** `setup.bat` (double-click, or from a normal `cmd`). It will:
   - Detect your GPU and pick the right environment
     (RTX 50xx → CUDA 12.8, everything older → CUDA 12.4).
   - Download the portable env (~5 GB, **one-time**) from Hugging Face.
   - Download + verify the public tracking models (~12 GB, hash-checked).
   - Run a self-test and create a Desktop shortcut.
3. **Body models (one-time, licensed):** SMPL and SMPL-X are **not** included
   (Max Planck license). Download them yourself and point the GUI to them:
   - SMPL-X: <https://smpl-x.is.tue.mpg.de/>
   - SMPL: <https://smpl.is.tue.mpg.de/>

When the self-test prints `RESULT: READY`, launch MocapOS from the Desktop icon.

### Tested GPUs
- **CUDA 12.8** build: RTX 50xx (Blackwell). Verified on RTX 5070 Ti.
- **CUDA 12.4** build: GTX 1000 / RTX 2000 / 3000 / 4000. Verified on GTX 1660 Ti.

---

## How it works

```
GitHub  (code, ~44 MB)          Hugging Face (weights, free)
  setup.bat ───────────────►  env_cu124.tar.gz / env_cu128.tar.gz
                              + public tracking models
SMPL / SMPL-X ── downloaded by the user (licensed)
```

The portable environments are hosted on Hugging Face at
[`LokoJeans/mocapos-envs`](https://huggingface.co/LokoJeans/mocapos-envs)
and fetched by `setup.bat`. Nothing heavy ever lives in git.

---

## Credits & Citation

MocapOS would not exist without **GVHMR** and **HaMeR**. If you use it, please cite
the original works:

```bibtex
@inproceedings{shen2024gvhmr,
  title={World-Grounded Human Motion Recovery via Gravity-View Coordinates},
  author={Shen, Zehong and Pi, Huaijin and Xia, Yan and Cen, Zhi and Peng, Sida
          and Hu, Zechen and Bao, Hujun and Hu, Ruizhen and Zhou, Xiaowei},
  booktitle={SIGGRAPH Asia Conference Papers},
  year={2024}
}

@inproceedings{pavlakos2024reconstructing,
  title={Reconstructing Hands in 3D with Transformers},
  author={Pavlakos, Georgios and Shan, Dandan and Radosavovic, Ilija and Kanazawa,
          Angjoo and Fouhey, David and Malik, Jitendra},
  booktitle={CVPR},
  year={2024}
}
```

## License

- MocapOS-authored code: [PolyForm Noncommercial 1.0.0](LICENSE-MocapOS.md)
- GVHMR (preserved): [`LICENSE`](LICENSE)
- All bundled components: [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)
