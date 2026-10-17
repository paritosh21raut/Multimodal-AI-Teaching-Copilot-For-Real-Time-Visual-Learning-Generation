# Output Modes

All modes share audio → STT → understanding → `LectureState`. They differ only in planner, composer, and display components.

| Mode | Name | Status | Output |
|---|---|---|---|
| A | **Live Slides** | V1 (done) | `SlideSpec` deck |
| B | **Concept Simulation** | V2 (S0, S1 done 2026-10-17) | a `simulation` block (`SimulationSpec`) inside a slide |
| C | **Story Scenes** | V3 | `StoryboardSpec` (scenes: visual, caption, motion, duration) |

## Mode selection
Per concept, never a global switch. A mode plugs in through **`RepresentationIntent`** (`core/events.py`, RULES #6):
a producer proposes a visual for some transcript lines (`visual_kind = simulation | story`, `template` ("" = values
for the open one), `strength` cue | setup | score | values | end, `values` heard, `reveal`, `origin` cue | policy | llm | teacher);
the presentation engine's policy decides and places it in the deck. Producers subscribe only to existing events
(`TranscriptFinal`, `UtteranceClassified`, `ConceptSignal`): audio, STT and understanding are unchanged. "Is a
visualization useful?" is the policy's decision (a setup with dynamics → yes; definitions / lists / history → no).

## Concept Simulation (V2) → F-014, contract `simulation-spec.md`, ADR-0010
- `simulation/detector.py` (spoken cue + values, 0 tokens) → `RepresentationIntent` → `presentation/simulations.py`
  (`SimulationController` in the engine: policy, placement beside the points, follow the explanation, teacher
  commands, the clock, simulation mode + recap) → `SlidePatch` → `web/sims/` (SVG scenes, one clock).
- Simulation mode (S1): a shown simulation is a slide of its own and pauses slide making; the talk meanwhile becomes
  a recap slide when the teacher goes back to the slides (`presentation/recap.py`).
- Templates are written by developers (Python solver + JS scene); the LLM never writes code or scenes. S0: block on a
  surface, incline; S1: pendulum, projectile, DC circuit, wave, orbit, unit circle → sine. Plan to S4 (processes; semiconductors, RLC, networks) and Explore mode: F-014 §2.
- The teacher's Full stage (`sim_full`) shows it full screen, like a zoomed image.

## Story Scenes (V3)
- First version: a storyboard of 3–6 scenes from retrieved images (or teacher images) with Ken Burns motion,
  captions, and a timeline, synchronized to the narration. See ADR-0006 for why this is not generative video. It
  uses the same `RepresentationIntent` path (`visual_kind = story`).
