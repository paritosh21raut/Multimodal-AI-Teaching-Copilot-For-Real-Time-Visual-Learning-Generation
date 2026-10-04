# ADR-0002: STT — local faster-whisper
Status: accepted (2026-10-05)

**Decision.** faster-whisper (CTranslate2) on CUDA, int8_float16, default `small.en`, with silero-vad
utterance segmentation. The final model is chosen in M1 after measuring latency/WER on the laptop.

**Why.** Free, offline, ≈ 1 GB VRAM, and fast enough for ≤ 2 s utterance latency. Cloud STT would add network dependency
and free-tier limits for something that runs continuously.

**Consequences.** Utterance-level (not word-streaming) transcripts; latency ≈ utterance end + ~0.5–1.5 s.
Multilingual later via model swap (`language` field already in the contract).
