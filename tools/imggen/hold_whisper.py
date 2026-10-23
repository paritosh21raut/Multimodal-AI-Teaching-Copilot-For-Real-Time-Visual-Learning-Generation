"""D1: hold the app's STT model on the GPU (as live), so gen_compare.py local measures SD-Turbo beside it.

    .venv/Scripts/python tools/imggen/hold_whisper.py [seconds]   prints READY once loaded and warmed
"""
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from faster_whisper import WhisperModel  # noqa: E402

from copilot.stt.cuda_dlls import register_nvidia_dlls  # noqa: E402
from copilot.stt.engine import SttConfig  # noqa: E402

register_nvidia_dlls()  # as the app does before its first CUDA call

cfg = SttConfig()
m = WhisperModel(cfg.model, device=cfg.device, compute_type=cfg.compute_type, download_root=str(ROOT / cfg.download_root))
list(m.transcribe(np.zeros(16000 * 2, dtype=np.float32), beam_size=1, language="en")[0])
print("READY", flush=True)
time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 600)
