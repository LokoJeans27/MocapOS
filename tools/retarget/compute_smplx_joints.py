"""Compute SMPL-X joint world positions per frame and save as .npz for comparison.

Runs in gvhmr conda env (needs torch + smplx model).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch

GVHMR_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GVHMR_ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rd = Path(args.results_dir)
    body = torch.load(str(rd / "hmr4d_results.pt"), map_location="cpu")
    p = body["smpl_params_global"]

    from hmr4d.utils.smplx_utils import make_smplx
    model = make_smplx("supermotion", use_pca=False, flat_hand_mean=True)
    with torch.no_grad():
        out = model(
            betas=p["betas"][:1].float(),
            global_orient=p["global_orient"].float(),
            body_pose=p["body_pose"].float(),
            transl=p["transl"].float(),
        )
    joints = out.joints[:, :22].cpu().numpy()  # (L, 22, 3) in Y-up world
    np.savez(args.out, joints=joints.astype(np.float32))
    print(f"Saved {joints.shape} joints to {args.out}")


if __name__ == "__main__":
    main()
