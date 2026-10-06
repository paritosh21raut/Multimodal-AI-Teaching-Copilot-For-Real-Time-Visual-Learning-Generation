# CLAUDE.md — Multimodal AI Teaching Copilot

Listens to a live lecture, understands topic/continuity/meaning, and renders a designed,
continuity-aware **live educational display** on the classroom projector. Later modes
(Concept Simulation, Story Scenes) reuse the same understanding core.

Branch: **`CLAUDE_rebuild` only.** Do not touch other branches. Do not inspect old code from other branches.
Original requirements: `docs/brief/master-prompt.md` (read only when requirements are in question).

## Session start protocol
1. Read `docs/STATE.md` (always). It states the current task and what is verified.
2. Load ONLY the docs the task needs (map below). Do not read all of `docs/`.
3. Inspect the relevant code, state a short plan, implement, test, runtime-verify,
   update docs + `STATE.md`, report, recommend a git checkpoint if a milestone is verified.

## What to load for which task
| Task area | Load |
|---|---|
| Any | `docs/STATE.md`, `docs/RULES.md` |
| Core/events/state | `docs/architecture/overview.md`, `docs/contracts/events.md`, `docs/contracts/lecture-state.md` |
| Audio / STT | `docs/architecture/audio-stt.md`, `docs/contracts/events.md` |
| Lecture understanding / LLM | `docs/architecture/understanding.md`, `docs/contracts/lecture-state.md`, ADR-0001 |
| Slide planning / composing | `docs/architecture/presentation.md`, `docs/contracts/slide-spec.md` |
| Live display / control view | `docs/architecture/display.md`, `docs/contracts/slide-spec.md`, ADR-0003, ADR-0005 |
| Images / diagrams | `docs/architecture/visuals.md`, `docs/contracts/slide-spec.md` |
| Persistence / recovery / post-lecture | `docs/architecture/persistence.md` |
| Simulation or Story modes | `docs/architecture/modes.md`, ADR-0006 |
| Testing work | `docs/TESTING.md` |
| Planning next milestone | `docs/ROADMAP.md` |
| Feature being built | its `docs/specs/F-xxx-*.md` |

## Role switching (adopt automatically)
| Task | Role |
|---|---|
| Architecture / interfaces | Systems Architect |
| Feature implementation | Senior Software Developer |
| STT, LLM, embeddings, ranking | AI/ML Engineer |
| Display, control view, rendering | Frontend / Real-Time Systems Engineer |
| Tests, verification | QA / Test Engineer |
| Latency, memory, VRAM | Performance Engineer |
| Failures, bugs | Senior Debugging Engineer |
| Recovery, secrets, robustness | Production / Systems Engineer |

## Non-negotiable rules (full list: `docs/RULES.md`)
- LLM is a gated reasoning service inside a deterministic core; it never controls flow.
- Never send the whole transcript to an LLM; context is bounded (see understanding.md).
- New concept ≠ new slide. Slide lifecycle decisions belong to the deterministic planner.
- UI (display/control) never mutates core state directly; it sends commands.
- No paid APIs, no Gemini. Free tiers + local only.
- Done = runs and produces the expected result. Mark unit-tested-only work as such.
- Don't edit tests to make them pass; don't add fake fallbacks.

## Commands
```bash
.venv/Scripts/python -m pip install -e ".[dev]"     # install
.venv/Scripts/python -m pip install -e ".[dev,audio,display,understanding,images]"   # full stack
.venv/Scripts/python tools/screenshot_lessons.py light human_body solar   # scripted lessons + real image search (0 LLM tokens)
.venv/Scripts/python tools/prompt_ab.py --dry <session>[:i,j]   # rebuild recorded prompts (0 tokens); without --dry: real A/B
.venv/Scripts/python -m pytest                      # fast tests
.venv/Scripts/python -m pytest -m slow              # + GPU/model tests
.venv/Scripts/python -m pytest -m browser           # real Edge via Playwright (display)
.venv/Scripts/python -m pytest -m live_llm tests/e2e/test_understanding_live.py -s   # real Groq (~1 min, uses free quota)
.venv/Scripts/python tools/screenshot_display.py    # all layouts, both themes -> artifacts/display (LOOK at them)
.venv/Scripts/python tools/screenshot_app.py        # run app, screenshot /control + /display -> artifacts/app
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --demo-slides --open
.venv/Scripts/python -m copilot.audio.mic_check     # list mics, record, transcribe
.venv/Scripts/python -m copilot --audio-file tests/fixtures/audio/photosynthesis_tts.wav
.venv/Scripts/python -m copilot                     # run app ([QUOTA] → ready → Enter → live; opens /control + /display, --no-open)
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --no-wait --speed 1   # M3 runtime check (real LLM)
```

## Git checkpoints
After a verified milestone: tell the user briefly, give exact commands and a concise message:
`git add -A && git commit -m "<type>: <msg>" && git push origin CLAUDE_rebuild`.
Do not commit tiny changes. Do not commit yourself unless asked.

## Reporting format
STATUS / IMPLEMENTED / TESTED / VERIFIED / ISSUES / NEXT — concise.
