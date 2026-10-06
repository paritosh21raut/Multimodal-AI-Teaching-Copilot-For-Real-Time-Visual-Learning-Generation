"""CLIP ViT-B/32 text-image similarity as ONNX on CPU (F-007b, ADR-0007). Never on the GPU (Whisper owns it).

Model: Xenova/clip-vit-base-patch32 (int8 text + vision encoders, ~150 MB) in `models/clip`. Preprocessing mirrors
the HF CLIPFeatureExtractor: RGB, bicubic resize of the shortest edge to 224, centre crop 224, /255, mean/std.
The text encoder pools at the end-of-text token, so padding uses that token (the first max id is the real one).
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Sequence

import numpy as np

log = logging.getLogger(__name__)

REPO = "Xenova/clip-vit-base-patch32"
SIZE = 224
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
EOT_ID = 49407
MAX_TOKENS = 77


def model_files(quantized: bool = True) -> tuple[str, str]:
    q = "_quantized" if quantized else ""
    return f"onnx/text_model{q}.onnx", f"onnx/vision_model{q}.onnx"


def preprocess(img) -> np.ndarray:
    """PIL image → (3, 224, 224) float32."""
    from PIL import Image

    img = img.convert("RGB")
    w, h = img.size
    scale = SIZE / min(w, h)
    img = img.resize((max(SIZE, round(w * scale)), max(SIZE, round(h * scale))), Image.BICUBIC)
    w, h = img.size
    left, top = (w - SIZE) // 2, (h - SIZE) // 2
    img = img.crop((left, top, left + SIZE, top + SIZE))
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - MEAN) / STD
    return arr.transpose(2, 0, 1)


def _normed(x: np.ndarray) -> np.ndarray:
    return (x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-12, None)).astype(np.float32)


class ClipScorer:
    def __init__(self, model_dir: Path, quantized: bool = True, threads: int = 2) -> None:
        self.model_dir = Path(model_dir)
        self.quantized = quantized
        self.threads = threads
        self._text = None
        self._vision = None
        self._tok = None
        self._lock = threading.Lock()  # one job at a time: CLIP shares the CPU with MiniLM and the event loop

    def ensure_downloaded(self) -> None:
        files = [*model_files(self.quantized), "tokenizer.json"]
        missing = [f for f in files if not (self.model_dir / f).exists()]
        if not missing:
            return
        from huggingface_hub import hf_hub_download

        log.info("downloading %s %s -> %s", REPO, missing, self.model_dir)
        for f in missing:
            hf_hub_download(REPO, f, local_dir=str(self.model_dir))

    def load(self) -> float:
        """Blocking: download if needed, create both ONNX sessions. Returns seconds taken."""
        t0 = time.perf_counter()
        self.ensure_downloaded()
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        tok.enable_truncation(MAX_TOKENS)
        tok.enable_padding(pad_id=EOT_ID, pad_token="<|endoftext|>")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = self.threads
        opts.inter_op_num_threads = 1
        text_f, vision_f = model_files(self.quantized)
        self._text = ort.InferenceSession(str(self.model_dir / text_f), opts, providers=["CPUExecutionProvider"])
        self._vision = ort.InferenceSession(str(self.model_dir / vision_f), opts, providers=["CPUExecutionProvider"])
        self._tok = tok
        return time.perf_counter() - t0

    @property
    def loaded(self) -> bool:
        return self._text is not None

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        if self._text is None or self._tok is None:
            raise RuntimeError("ClipScorer.load() was not called")
        with self._lock:
            enc = self._tok.encode_batch([t.lower() for t in texts])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            return _normed(self._text.run(None, {"input_ids": ids})[0])

    def embed_images(self, images: Sequence) -> np.ndarray:
        """PIL images → L2-normalised (n, 512)."""
        if self._vision is None:
            raise RuntimeError("ClipScorer.load() was not called")
        if not images:
            return np.zeros((0, 512), dtype=np.float32)
        batch = np.stack([preprocess(i) for i in images])
        with self._lock:
            return _normed(self._vision.run(None, {"pixel_values": batch})[0])

    def scores(self, query: str, images: Sequence) -> list[float]:
        """Cosine similarity of each image to the query (CLIP scale: ~0.15 unrelated … ~0.35 a clear match)."""
        if not images:
            return []
        t = self.embed_texts([query])
        return [float(x) for x in (self.embed_images(images) @ t[0])]
