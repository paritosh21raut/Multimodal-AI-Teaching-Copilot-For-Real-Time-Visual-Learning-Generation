# ADR-0002: STT — local faster-whisper
Status: accepted (2026-10-05)

**Decision.** faster-whisper (CTranslate2) on CUDA, int8_float16, default `small.en`, with silero-vad
utterance segmentation. The final model is chosen in M1 after measuring latency/WER on the laptop.

**Why.** Free, offline, ≈ 1 GB VRAM, and fast enough for ≤ 2 s utterance latency. Cloud STT would add network dependency
and free-tier limits for something that runs continuously.

**Consequences.** Utterance-level (not word-streaming) transcripts; latency ≈ utterance end + ~0.5–1.5 s.
Multilingual later via model swap (`language` field already in the contract).

## Measurements (2026-10-05, RTX 3050 Laptop 4 GB, int8_float16, beam 1, 30 s TTS clip / 14 s clip)
| Model | Infer 14 s clip (warm) | VRAM (model) | Notes |
|---|---|---|---|
| distil-small.en | 0.23 s | ~350 MB | |
| small.en | 0.33 s | ~440 MB | low-resource option |
| **medium.en** | 0.75 s | ~1.1 GB | **default**; best accuracy expected on accented classroom speech |
| large-v3-turbo | 0.57 s | ~1.2 GB | no punctuation in our test; candidate for V5 multilingual |

End-to-end in the app (real-time WAV): utterance end detected → `TranscriptFinal` p50 673 ms, p95 709 ms.
Plus 600 ms VAD hangover ⇒ ~1.3 s from end of speech to text. Revisit the default after real-mic accuracy tests.
CUDA libs: `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` wheels, registered at runtime (`copilot.stt.cuda_dlls`).
