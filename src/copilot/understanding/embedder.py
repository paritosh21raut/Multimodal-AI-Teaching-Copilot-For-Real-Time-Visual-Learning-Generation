"""Sentence embeddings: all-MiniLM-L6-v2 as ONNX on CPU (onnxruntime + tokenizers; no torch)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np

log = logging.getLogger(__name__)

_FILES = ("onnx/model.onnx", "tokenizer.json")


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """L2-normalised float32 vectors, shape (len(texts), dim)."""
        ...


class MiniLmEmbedder:
    dim = 384

    def __init__(self, model_dir: Path, repo: str = "sentence-transformers/all-MiniLM-L6-v2",
                 max_len: int = 128, threads: int = 2) -> None:
        self.model_dir = Path(model_dir)
        self.repo = repo
        self.max_len = max_len
        self.threads = threads
        self._session = None
        self._tok = None
        self._lock = threading.Lock()  # onnxruntime sessions are thread-safe, the tokenizer config is not

    def ensure_downloaded(self) -> None:
        missing = [f for f in _FILES if not (self.model_dir / f).exists()]
        if not missing:
            return
        from huggingface_hub import hf_hub_download

        log.info("downloading %s %s -> %s", self.repo, missing, self.model_dir)
        for f in missing:
            hf_hub_download(self.repo, f, local_dir=str(self.model_dir))

    def load(self) -> float:
        """Blocking: download if needed, create the ONNX session. Returns seconds taken."""
        t0 = time.perf_counter()
        self.ensure_downloaded()
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        tok.enable_truncation(self.max_len)
        tok.enable_padding(pad_id=0, pad_token="[PAD]")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = self.threads
        opts.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(self.model_dir / "onnx" / "model.onnx"), opts, providers=["CPUExecutionProvider"]
        )
        self._tok = tok
        self._input_names = {i.name for i in self._session.get_inputs()}
        return time.perf_counter() - t0

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if self._session is None or self._tok is None:
            raise RuntimeError("MiniLmEmbedder.load() was not called")
        with self._lock:
            enc = self._tok.encode_batch(list(texts))
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self._session.run(None, feeds)[0]  # (batch, seq, dim)
        m = mask[..., None].astype(np.float32)
        pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return (pooled / np.clip(norms, 1e-12, None)).astype(np.float32)
