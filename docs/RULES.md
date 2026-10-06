# Development Rules

## Architecture
1. **Deterministic core, gated LLM.** All flow control, state transitions, and slide lifecycle are code.
   The LLM only answers bounded, schema-validated questions.
2. **Bounded context.** An LLM prompt is built from: lecture header, rolling summary, current slide
   summary, and the new transcript window. Hard token budget per call (see understanding.md).
   The full transcript is never sent.
3. **Single writer.** Only `LectureStateStore` mutates `LectureState`. Everything else emits events
   or commands.
4. **UI is a client.** Display and Control View consume published state/patches and send commands.
   They never import pipeline modules or block the pipeline.
5. **Live display ≠ PPTX.** PPTX is a post-lecture export from the archived `SlideSpec`s.
6. **Modes are plug-ins.** New modes consume `LectureState` + `RepresentationIntent`; they must not
   require changes to audio, STT, or understanding.
7. **Language-aware interfaces.** Text-bearing contracts carry a `language` field (English only for now).
8. **Teacher is the authority; the projector is truthful.** Display content comes from the lecture, written as
   clear slide text (not transcript copies; definitions exact). Additions are small and level-appropriate. A
   factual, conceptual or formula mistake is shown corrected (when the model is confident) and always reported in
   the Control View with what was said; the teacher can switch back with one click. Misheard words (spelling /
   pronunciation) are corrected without a card and logged in the terminal (user decision 2026-10-06).

## Code
- Python 3.10, type hints everywhere, Pydantic v2 models for all contracts.
- asyncio for the pipeline; CPU/GPU-heavy work runs in executors/threads, never on the event loop.
- Every external call (LLM, HTTP, model load) has a timeout and an explicit failure path.
- No silent `except: pass`. Failures are logged and surfaced as events.
- Config via `config/default.toml` + `.env` (secrets). No hard-coded keys.
- Keep modules small and single-purpose. Match surrounding style.

## Testing and "done"
- Tests must assert real behaviour. Don't change a test to make it pass unless you prove the test is wrong.
- No fake fallback outputs created to satisfy tests.
- A feature is **done** only when it is implemented, tested, and **runtime-verified**
  (actually run: simulator, real mic, browser screenshot, as applicable).
- Record verification status honestly in `docs/STATE.md`: `verified`, `unit-tested only`, `not started`.
- For critical components: implement → independent review (separate subagent) → test → fix → verify.

## Documentation
- Update the relevant architecture/contract doc when an interface changes.
- Write a short feature spec in `docs/specs/` before building a non-trivial feature.
- Record significant decisions as ADRs in `docs/decisions/`.
- Keep every doc short. Prefer tables and lists over prose.

## Cost
- No paid APIs or tools. No Gemini. Free tiers (Groq, OpenRouter free models) and local models only.
