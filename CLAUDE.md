# CLAUDE.md — Multimodal AI Teaching Copilot

Listens to a live lecture and renders a continuity-aware live educational display on the projector.
V1 = live slides (done). V2 = Concept Simulation: S0–S4 templates (done); **V2 Next = F-015 Live Scene Engine**
(open-vocabulary scenes from speech, no templates). V3 Story Scenes, V4 Multilingual reuse the same core.

Branch: **`V2-Concept-Simulation`** (holds all of V1; V1 fixes go here). `CLAUDE_rebuild` = V1, untouched unless
asked. Do not inspect other branches. Original requirements: `docs/brief/master-prompt.md` (only if in question).

## Session protocol (token budget matters)
1. Read `docs/STATE.md` (short). It names the current session card.
2. Read that card (`docs/v2/Lx-*.md`) and ONLY the files it lists. Need something else? grep / read a line range,
   don't read whole large files. Never read `docs/history/` unless asked.
3. Short plan → implement → tests for the touched area → runtime check → one review subagent on the diff → update
   the card's Result (≤ 1 KB) + `STATE.md` (≤ 3 KB) → report → recommend a commit.
4. Stop at the card's stop point; the next part starts in a fresh session.

## Working lean
- Tests: `pytest -q -x --no-header <paths> | tail -20`; browser tests for touched files; the full suite once at the end.
- Screenshots: one contact sheet per theme, not one image per scene.
- Agents: an Explore agent only for a broad search of unknown old code; one review subagent per session. No others.
- Live LLM runs: one small run per session; state the token estimate first and the tokens used after.
- Docs: a spec ≤ 8 KB, a card ≤ 5 KB; results go to `docs/history/`, not into specs.
- Commands: `docs/COMMANDS.md` (read only when needed).

## Doc map (load only what the task needs)
| Task | Load |
|---|---|
| V2 Next (scene engine) | current card in `docs/v2/`, `docs/v2/F-015-live-scene-engine.md`, `docs/contracts/scene-spec.md` |
| Old templates (only if a card says) | `docs/specs/F-014-concept-simulation.md`, `docs/contracts/simulation-spec.md`, ADR-0010 |
| Rules in question | `docs/RULES.md` |
| Core / events / state | `docs/architecture/overview.md`, `docs/contracts/events.md`, `docs/contracts/lecture-state.md` |
| Audio / STT | `docs/architecture/audio-stt.md` |
| Understanding / LLM | `docs/architecture/understanding.md`, ADR-0001 |
| Slides | `docs/architecture/presentation.md`, `docs/contracts/slide-spec.md` |
| Display / control | `docs/architecture/display.md` (grep it, 25 KB), ADR-0003, ADR-0005 |
| Images | `docs/architecture/visuals.md` |
| Persistence | `docs/architecture/persistence.md` |
| V3 Story | `docs/v3/V3-story-outline.md`, ADR-0006 |
| Testing / roadmap | `docs/TESTING.md` / `docs/ROADMAP.md` |

## Roles (adopt automatically)
Architecture → Systems Architect · features → Senior Developer · LLM/STT/ranking → AI/ML Engineer · display/rendering →
Frontend / Real-Time Engineer · tests → QA · latency/VRAM → Performance · bugs → Debugging · robustness → Production.

## Non-negotiable rules (full list: `docs/RULES.md`)
- The LLM is a gated reasoning service inside a deterministic core; it never controls flow, never writes code, and
  never computes physics: it states WHAT is in a scene, engines compute HOW.
- Never send the whole transcript to an LLM; context is bounded.
- New concept ≠ new slide; the deterministic planner owns the slide lifecycle.
- UI never mutates core state; it sends commands.
- No paid APIs, no Gemini. Groq free tier (several keys) + local only.
- Done = runs and gives the expected result. Mark unit-tested-only work as such.
- Don't edit tests to make them pass; no fake fallbacks. Never print a number the teacher didn't say or Python didn't compute.

## Git checkpoints
After a verified milestone, give: `git add -A && git commit -m "<type>: <msg>" && git push origin V2-Concept-Simulation`.
Don't commit tiny changes; don't commit unless asked.

## Reporting format
STATUS / IMPLEMENTED / TESTED / VERIFIED / ISSUES / NEXT — concise.
