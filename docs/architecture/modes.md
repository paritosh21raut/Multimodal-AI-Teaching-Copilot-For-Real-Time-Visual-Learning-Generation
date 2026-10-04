# Output Modes

All modes share audio → STT → understanding → `LectureState`. They differ only in planner, composer, and display components.

| Mode | Name | Status | Output |
|---|---|---|---|
| A | **Live Slides** | MVP | `SlideSpec` deck |
| B | **Concept Simulation** | V3 | `SimulationSpec` (template id + parameters + annotations) |
| C | **Story Scenes** | V4 | `StoryboardSpec` (scenes: visual, caption, motion, duration) |

## Mode selection
Per concept, not global: the Planner can embed a simulation or storyboard **as a block** inside a slide when the
`RepresentationIntent` says it helps (`visual_kind=simulation|story`), or the teacher can switch the display mode.
"Is a visualization useful?" is a policy decision (mechanism/motion/field/process with dynamics → yes;
definitions/lists → no).

## Concept Simulation (V3)
- A library of parametric templates written by developers, not the LLM: block on a surface/incline with force
  arrows, pulley, simple circuit, wave propagation, orbit, pendulum, cell cycle, water cycle, geometric transforms.
- The LLM picks a template and fills validated parameters (e.g. mass, angle, μ, which forces to show).
- Rendered with SVG/Canvas; physics through matter.js only where needed. It runs at 60 fps on the laptop iGPU/dGPU.

## Story Scenes (V4)
- First version: a storyboard of 3–6 scenes from retrieved images (or teacher images) with Ken Burns motion,
  captions, and a timeline, synchronized to the narration. See ADR-0006 for why this is not generative video.
