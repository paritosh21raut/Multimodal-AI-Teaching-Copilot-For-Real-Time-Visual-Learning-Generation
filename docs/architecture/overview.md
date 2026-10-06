# Architecture Overview

## Principles
- **Deterministic event-driven core.** Components are asyncio workers that communicate only through
  typed events on an in-process `EventBus`.
- **Single-writer state.** `LectureStateStore` owns `LectureState`; it applies events and publishes snapshots.
- **LLM as a bounded service.** It is called only by the Interpreter (and post-lecture jobs), through a gate,
  a rate limiter, and schema validation.
- **Progressive rendering.** A fast deterministic update first, then LLM-refined content, then async enrichment (images).
- **Everything is logged.** An append-only event log (SQLite) enables recovery, debugging, and post-lecture outputs.

## Pipeline
```
 ┌──────────── process: copilot (Python, asyncio) ────────────────────────────────────────────┐
 │ AudioCapture ─► VAD ─► STT worker ──TranscriptFinal──► UtteranceFilter                     │
 │                                                          │ ContentUtterance                │
 │                                                          ▼                                 │
 │                     ConceptTracker (embeddings) ─► DiscourseBuffer ─► Gate                 │
 │                                                                         │ InterpretRequest │
 │                                                                         ▼                  │
 │                                          Interpreter ──► LLM Router (Groq keys; Ollama opt-in)│
 │                                                │ Interpretation                            │
 │                                                ▼                                           │
 │   Commands ─────────────────────────► LectureStateStore ──StateChanged──► Planner          │
 │   (control view)                                                          │ SlideOps       │
 │                                                                           ▼                │
 │                                         Composer ─► SlideDeck ──SlidePatch──► DisplayHub   │
 │                                         Enrichers (images) ──SlidePatch──┘    │ WebSocket  │
 │   EventLog (SQLite) ◄── all events                                            │            │
 └───────────────────────────────────────────────────────────────────────────────┼────────────┘
                     Browser: /display (projector, full screen)   /control (teacher laptop)
```

## Component responsibilities
| Component | Package | Responsibility |
|---|---|---|
| App/lifecycle | `copilot.app` | Startup, readiness, Enter to start, shutdown, CLI |
| Core | `copilot.core` | Events, EventBus, config, logging, clock, ids |
| Audio | `copilot.audio` | Mic capture, VAD, utterance segmentation |
| STT | `copilot.stt` | faster-whisper inference in a worker thread |
| Understanding | `copilot.understanding` | Filter, concept tracker, buffer, gate, interpreter, rolling memory |
| LLM | `copilot.llm` | Providers, router/fallback, rate limiting, JSON validation, prompt budget |
| Presentation | `copilot.presentation` | `SlideSpec` models, planner, capacity model, composer, deck |
| Visuals | `copilot.visuals` | Image retrieval/ranking/cache, diagram data |
| Display | `copilot.display` | FastAPI server, WebSocket hub, command intake, static web |
| Persistence | `copilot.persistence` | Event log, snapshots, session archive |
| Post-lecture | `copilot.postlecture` | Notes, summaries, quiz, PPTX (offline jobs) |
| Simulator | `copilot.sim` | Script → timed transcript events (replaces audio + STT) |

## Lifecycle states
`STARTING → READY → LIVE ⇄ PAUSED → ENDING → ENDED` (`FAILED` reachable from any state, with a reason).
In READY the terminal prompts "Press Enter to start the lecture"; the Control View shows the same.

## Threading model
- One asyncio loop for orchestration.
- STT, embeddings, and CLIP run in dedicated worker threads (bounded queues; drop or merge on backpressure, never block capture).
- Audio capture uses the sounddevice callback thread → thread-safe queue.

## Mode extension point
`Renderer`-style output strategies subscribe to `StateChanged` + `RepresentationIntent`.
Live Slides is the first. Concept Simulation and Story Scenes are added as new planners/composers and
new display components — see `modes.md`.
