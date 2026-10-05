# ADR-0008: Concept embeddings via ONNX, not sentence-transformers
Status: accepted (2026-10-05)

**Context.** The ConceptTracker needs MiniLM sentence embeddings on every content utterance. `sentence-transformers`
pulls in PyTorch (~2 GB with CUDA), which the project does not otherwise need; the GPU is reserved for Whisper.

**Decision.** Run `sentence-transformers/all-MiniLM-L6-v2` from its official ONNX export with `onnxruntime` (CPU,
already installed for Silero VAD) and HF `tokenizers` (already installed for faster-whisper); mean pooling + L2
normalisation in numpy. The model (~90 MB) downloads to `models/minilm` during STARTING.

**Consequences.** + No torch, ~0.5 s load, ~6 ms/sentence on CPU, no VRAM. − We own ~40 lines of pooling code
(tested against semantic expectations in `tests/integration/test_embedder_real.py`). If the model cannot load,
the tracker degrades to cue words only (logged, `ErrorRaised`).
