import os
from pathlib import Path
import torch

PROJ_ROOT = Path(__file__).resolve().parents[1]

# Patch torch.load for PyTorch 2.6+ compatibility (weights_only defaults to True)
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load


def os_chdir_to_proj_root():
    """useful for running notebooks in different directories."""
    os.chdir(PROJ_ROOT)
