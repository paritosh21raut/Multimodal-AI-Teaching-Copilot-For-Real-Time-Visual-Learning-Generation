# Audio + Speech-to-Text

## Capture
- `sounddevice.InputStream`, 16 kHz mono float32, 30 ms blocks → thread-safe ring queue.
- Device is selectable in config; the default is the system default input (lapel/wireless mic expected).
- Mic loss → `AudioDeviceLost` event; retry with backoff; Control View shows the warning.

## Voice activity detection
- silero-vad (ONNX, CPU). Speech start/end with hangover (end silence ≈ 600 ms).
- Utterances are capped at ≈ 15 s (forced split at the lowest-energy point), so latency stays bounded. The
  silence run is clipped to the frames kept after a split (a cut inside a pause once crashed the audio thread,
  live test 2026-10-05). A segmenter error drops only the pending utterance (`UtteranceDropped`,
  reason `segmenter_error`); the lecture continues.
- Very short segments (< 300 ms) are dropped as noise.

## STT
- faster-whisper on CUDA, `compute_type=int8_float16`. Default model `small.en` (≈ 1 GB VRAM).
  `distil-small.en` and `medium.en` are configurable. The model is chosen in M1 after measuring WER/latency.
- Runs in a dedicated thread; one utterance at a time; `beam_size` 1–2; `condition_on_previous_text=False`
  (avoids hallucination loops), plus a short `initial_prompt` with the subject/topic keywords for vocabulary priming.
- Emits `TranscriptFinal` (text, start/end time, avg logprob, no_speech_prob, language="en").
- Optional partials (`TranscriptPartial`) for long utterances, used only by the Control View.
- Hallucination guard: drop segments with high no_speech_prob or known filler hallucinations ("Thank you.", repeats).

## Budgets
- End-of-utterance → `TranscriptFinal`: ≤ 2 s target.
- VRAM ≤ 1.5 GB; leaves headroom for optional local models.

## Future (V5)
- Multilingual models (`small`/`medium` multilingual, IndicWhisper). `language` is already in the contract.
