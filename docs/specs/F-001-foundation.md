# F-001: Foundation (M0)

## Scope
- Package `copilot` (src layout), `pyproject.toml`, `config/default.toml`, `.env.example`.
- `core.events`: base `Event` + M0 events (`LifecycleChanged`, `TranscriptFinal`, `CommandReceived`, `StateChanged`) + `TranscriptSegment`, `Command`.
- `core.bus.EventBus`: typed subscribe/publish; per-subscriber bounded queue with an overflow policy (`block`, `drop_oldest`); wildcard subscription; clean shutdown.
- `core.config`: TOML defaults + optional user TOML + env overrides (`COPILOT__SECTION__KEY`); secrets from `.env`.
- `core.state`: `LectureState` models + `LectureStateStore` (single writer). M0 handles lifecycle, transcript stats, and the setup.
- `persistence.event_log.EventLog`: SQLite append-only log of all events, batched writer.
- `sim`: lecture script parser + `LectureSimulator` that publishes `TranscriptFinal` at realistic pace (speed factor).
- `app`: `python -m copilot` → STARTING → READY (prints readiness, waits for Enter unless `--no-wait`) → LIVE → ENDED.
  `--simulate <script>` feeds the simulator; Ctrl+C or the end of the script → graceful end.

## Lecture script format (`tests/fixtures/lectures/*.txt`)
```
# comment (ignored)
@setup subject=Biology grade=7 topic=Photosynthesis
@expect topic=Photosynthesis subtopic=Definition act=definition slide=new
Photosynthesis is the process by which green plants make their own food.
[pause 2.5]
```
- Every non-directive line is one utterance. Its duration = words / 150 wpm (min 1 s).
- `@expect` annotations attach to the next utterance (used by later understanding/presentation tests).

## Acceptance
- Unit tests: bus ordering/fan-out/overflow/shutdown; config precedence; state store versioning; script parser; event log round-trip.
- Integration: simulator → bus → state store + event log; stats match the script; events persisted in order.
- Runtime: `python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --no-wait --speed 20` runs to ENDED, prints the event summary, and the SQLite file contains the events.
