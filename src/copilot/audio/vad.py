"""Streaming Silero VAD (v6 ONNX model bundled with faster-whisper)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

FRAME = 512  # samples at 16 kHz = 32 ms
CONTEXT = 64


def default_model_path() -> Path:
    import faster_whisper

    path = Path(faster_whisper.__file__).parent / "assets" / "silero_vad_v6.onnx"
    if not path.exists():
        raise FileNotFoundError(f"Silero VAD model not found at {path}")
    return path


class SileroVad:
    """Feed exactly FRAME samples at a time; returns the speech probability of that frame."""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        import onnxruntime

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 4
        self._session = onnxruntime.InferenceSession(
            str(model_path or default_model_path()), providers=["CPUExecutionProvider"], sess_options=opts
        )
        self.reset()

    def reset(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros(CONTEXT, dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        if frame.shape != (FRAME,):
            raise ValueError(f"expected {FRAME} samples, got {frame.shape}")
        x = np.concatenate([self._context, frame.astype(np.float32, copy=False)])[None, :]
        prob, self._h, self._c = self._session.run(None, {"input": x, "h": self._h, "c": self._c})
        self._context = frame[-CONTEXT:].astype(np.float32, copy=True)
        return float(np.asarray(prob).reshape(-1)[0])
