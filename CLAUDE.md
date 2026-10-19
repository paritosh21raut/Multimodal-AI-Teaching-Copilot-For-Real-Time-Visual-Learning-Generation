# CLAUDE.md — Multimodal AI Teaching Copilot

Listens to a live lecture, understands topic/continuity/meaning, and renders a designed,
continuity-aware **live educational display** on the classroom projector. V1 = live slides (done). V2 = **Concept
Simulation** (live parametric simulations inside slides); V3 Story Scenes, V4 Multilingual reuse the same core.

Branch: **`V2-Concept-Simulation`** (from `CLAUDE_rebuild` 029002c, 2026-10-17). It holds all of V1, so V1 fixes are
made here too. `CLAUDE_rebuild` = V1, untouched unless the user asks. Do not inspect old code from other branches.
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
| Concept Simulation (V2) | `docs/specs/F-014-concept-simulation.md`, `docs/contracts/simulation-spec.md`, ADR-0010, `docs/architecture/modes.md` |
| Story Scenes (V3) | `docs/architecture/modes.md`, ADR-0006 |
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
.venv/Scripts/python tools/replay_interpretations.py <session> light --images   # recorded LLM answers + real image search (0 tokens)
.venv/Scripts/python tools/materials_check.py <session>   # lecture-material prompts from a recorded lecture (0 tokens); --live: real Groq + files
.venv/Scripts/python tools/quiz_check.py <session> [--count 15]   # quiz/test prompt from a recorded lecture (0 tokens); --live: one real set
.venv/Scripts/python tools/paper_eval.py latency <session...>   # paper: end-to-end latency from live logs (0 tokens)
.venv/Scripts/python tools/baseline_llm_slides.py <session> [--metrics]   # paper: LLM-controlled baseline (~700 tok/unit); --metrics 0 tokens
.venv/Scripts/python tools/eval_test.py run --note "..." [-- <copilot args>]   # paper validation test -> verify_results/testN; see docs/paper/VALIDATION.md
.venv/Scripts/python tools/eval_sheets.py sheets|score   # paper: annotation workbooks + T1-T3 rating form / scores -> verify_results/_eval
PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/build_docx.py <out.docx>   # paper; render.ps1 <docx> <pdf> prints pages
.venv/Scripts/python tools/v1_eval.py [--out f.json] [--compare verify_results/_eval/v1_baseline.json]   # F-013 metrics from event logs (0 tokens)
.venv/Scripts/python tools/v1_eval.py --replay | --gate   # F-013: engine replay (cues off/on) / gate replay (call floors), 0 tokens
.venv/Scripts/python tools/v1_eval.py --structure [names] [--out f.json]   # F-013 S2: boundaries vs annotators, part rate, child slides (0 tokens)
.venv/Scripts/python tools/v1_eval.py --s3 [names] [--list verbatim,garbage,dup,def,table,formula] [--out f.json]   # F-013 S3: representation (0 tokens)
.venv/Scripts/python tools/screenshot_s3.py [groups facts members definition formula trig compare3 tiles named_eq maxwell motion cards]   # S3 layouts + mistake cards, both themes -> artifacts/display
.venv/Scripts/python tools/prompt_ab.py --compare <session>[:i,j]   # F-013 S3b: N-way comparison rule A/B (real Groq; --dry 0 tokens)
.venv/Scripts/python tools/prompt_ab.py --said [--both|--old] <session>[:i,j]   # F-013 S3c: "never state a fact not said" A/B (real Groq)
.venv/Scripts/python tools/figure_check.py <notes.pdf ...> --ask "STM32 block diagram"   # F-013 S4: asked figure end to end (own files, web; 0 tokens) -> artifacts/figures
.venv/Scripts/python tools/make_figure_fixture.py   # F-013 S4: tests/fixtures/notes/drawn_figures.pdf (vector figures + table + note)
.venv/Scripts/python tools/screenshot_structure.py   # S2: nested Lecture Structure + child crumb, both themes -> artifacts/display
.venv/Scripts/python tools/screenshot_cues.py      # announced slide / heard list / interpreted, both themes -> artifacts/display
.venv/Scripts/python tools/v2_eval.py values|sessions|detect [names] [--list]   # F-014: values corpus P/R, 2026-10-17 sessions, detector replay vs annotations (0 tokens)
.venv/Scripts/python tools/screenshot_sims.py [light dark] [scene names]   # F-014 scenes (13 templates incl. S3 processes), sim mode + recap -> artifacts/sims (LOOK at them)
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
.venv/Scripts/python -m copilot --mode high          # this run in high performance (default: the /control Speed switch, kept in data/preferences.json)
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --no-wait --speed 1   # M3 runtime check (real LLM)
```

## Git checkpoints
After a verified milestone: tell the user briefly, give exact commands and a concise message:
`git add -A && git commit -m "<type>: <msg>" && git push origin V2-Concept-Simulation`.
Do not commit tiny changes. Do not commit yourself unless asked.

## Reporting format
STATUS / IMPLEMENTED / TESTED / VERIFIED / ISSUES / NEXT — concise.
