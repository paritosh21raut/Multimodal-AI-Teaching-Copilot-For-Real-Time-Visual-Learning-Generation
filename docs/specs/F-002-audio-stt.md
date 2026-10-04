# F-002: Audio capture + VAD + STT (M1)

## Components
| Module | Role | Thread |
|---|---|---|
| `audio.sources` | `MicSource` (sounddevice, 16 kHz mono, 512-sample blocks) and `WavFileSource` (plays a WAV at ×speed, for tests) | callback / feeder thread |
| `audio.vad.SileroVad` | streaming Silero v6 ONNX (bundled with faster-whisper): 512-sample frame + 64-sample context, LSTM state carried | audio thread |
| `audio.segmenter.UtteranceSegmenter` | pure state machine: frame probs → utterances (pre-roll, hangover, min length, max length split at the lowest-prob frame) | audio thread |
| `stt.engine.WhisperEngine` | faster-whisper wrapper + hallucination guard | STT thread |
| `stt.pipeline.SpeechPipeline` | wires source → VAD → segmenter → STT; publishes events to the bus thread-safely | owns both threads |

## Behaviour
- Lecture time = audio sample clock (samples / 16 000), so it is deterministic and independent of wall clock.
- Segmenter defaults: start prob ≥ 0.5, end prob < 0.35, end after 600 ms silence, 200 ms pre-roll/post-pad,
  drop < 300 ms, force-split at 15 s (lowest-prob frame in the last 3 s).
- STT: `medium.en` by default (measured on the RTX 3050: 0.75 s per 14 s of audio, ~1.1 GB VRAM; `small.en` 0.33 s / ~440 MB),
  `int8_float16`, `condition_on_previous_text=False`, `initial_prompt` from the setup (subject/topic).
- Hallucination guard: drop if (no_speech_prob > 0.6 and avg_logprob < -1.0), compression_ratio > 2.4,
  or text is a known filler hallucination ("thank you.", "thanks for watching", "you") for short utterances.
- Events: `TranscriptFinal` (+ `stt_latency_ms` = utterance end detected → text ready), `AudioLevel` (≤ 5 Hz),
  `AudioDeviceLost`, `UtteranceDropped` (reason).
- Backlog: the utterance queue is unbounded but a warning is emitted when > 3 are pending (STT falling behind).
- The model loads during STARTING (before READY), and the mic opens at LIVE.

## Acceptance
- Unit: segmenter on synthetic probability sequences (start/end/hangover/min/max split, pre-roll); hallucination guard.
- Integration: TTS WAV fixture with inserted silences → WavFileSource → real VAD + real Whisper → expected sentences
  (word-level match ≥ 90%), lecture timestamps monotonic. Marked `slow` (needs GPU + model).
- Runtime: `python -m copilot --audio-file <wav>` and a real-mic run; record latency and VRAM in STATE.md.
