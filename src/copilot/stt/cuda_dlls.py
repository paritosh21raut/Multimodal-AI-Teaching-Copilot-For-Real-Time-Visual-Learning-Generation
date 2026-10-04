"""Make pip-installed NVIDIA DLLs (nvidia-cublas-cu12, nvidia-cudnn-cu12) loadable on Windows.

CTranslate2 loads cuBLAS/cuDNN lazily via the normal DLL search path, so the venv's
`site-packages/nvidia/*/bin` directories must be registered before the first CUDA call.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_done = False


def register_nvidia_dlls() -> list[str]:
    global _done
    if _done or sys.platform != "win32":
        return []
    _done = True
    added: list[str] = []
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in sorted(nvidia.glob("*/bin")):
            os.add_dll_directory(str(bin_dir))
            added.append(str(bin_dir))
    if added:
        # Some DLLs resolve their own dependencies through PATH, not the added directories.
        os.environ["PATH"] = os.pathsep.join(added + [os.environ.get("PATH", "")])
    return added
