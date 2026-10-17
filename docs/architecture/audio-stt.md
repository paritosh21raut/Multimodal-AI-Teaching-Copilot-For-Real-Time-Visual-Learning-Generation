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
  F-012: + "Terms: …" with ≤ 30 words from the study material in use that MiniLM's WordPiece vocabulary does not know
  and that are seen at least twice (`notes.reference.rare_terms`: GPIO, sinoatrial, thylakoid), fixed when speech
  starts. Not yet measured on real audio with study material. F-013 S3b: the prompt grows with the lecture glossary
  (`VocabularyChanged` → `SpeechPipeline.set_prompt`, terms ≤ 60 words, newest kept). On medium.en a 59-word prompt
  is not slower (f013 WAV, 8 s chunks). A listed term can be echoed in a garbled chunk; check on the real mic.
- Emits `TranscriptFinal` (text, start/end time, avg logprob, no_speech_prob, language="en").
- **Live partials (F-013 S1b).** A second, fast model (`[stt] partial_model = "distil-small.en"`, own thread, own
  CTranslate2 instance) transcribes the utterance in progress every `partial_interval_s` (0.8 s; latest snapshot only,
  never queued) → `TranscriptPartial(utterance, text, stable)`. `stable` = the words two consecutive passes agree on
  (local agreement); only it is used. It runs **without** the vocabulary prompt: the 30 study-material terms made
  distil-small.en ~10x slower (1.4 s instead of 0.15 s per pass, RTX 3050). Benchmark (RTX 3050 4 GB): 0.13–0.2 s per
  pass alone, 0.2–0.36 s while medium.en is busy. The final text stays medium.en with the prompt.
- **Sentence cuts.** When the agreed live text has a finished sentence followed by ≥ 2 more agreed words, the
  segmenter ends the utterance there (`split_at`: quietest frame within 0.25 s of the word end), so medium.en
  transcribes sentence by sentence even when the speaker does not pause (tests 1–30: 25 % of lines held several
  sentences, p90 line 13.5 s). Every `TranscriptFinal` carries its `utterance` number, linking it to its partials.
  F-013 performance mode: only in **high**. In **standard** (the default) the lines stay the speaker's utterances
  (`SpeechPipeline.set_split(False)`, also mid-lecture); the live text and its instant display are the same in both.
- Hallucination guard: drop segments with high no_speech_prob or known filler hallucinations ("Thank you.", repeats).

## Budgets
- End-of-utterance → `TranscriptFinal`: ≤ 2 s target.
- VRAM ≤ 1.5 GB; leaves headroom for optional local models.

## Future (V5)
- Multilingual models (`small`/`medium` multilingual, IndicWhisper). `language` is already in the contract.
