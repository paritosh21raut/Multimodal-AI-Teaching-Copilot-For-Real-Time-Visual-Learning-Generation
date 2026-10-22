# L3 — Any subject, continuity, teacher control (session card)

**Goal:** non-physics subjects get scenes too, the scene follows the lecture's edits reliably, and the teacher controls it.
Examples: "blood leaves the left ventricle through the aorta…", "water evaporates, condenses into clouds…",
"push 3, push 5, pop", "BFS from node A", "demand rises, the curve shifts right", "sodium gives its electron to chlorine".

## Read
1. `docs/v2/F-015-live-scene-engine.md` §2, §5, §7
2. `docs/contracts/scene-spec.md`
3. `src/copilot/scene/compiler.py` (prompt + context builder) and `scene/ops.py`
4. `src/copilot/presentation/scenes.py` (command handling) + grep `/control` sim bar in `web/control/`
5. `src/copilot/simulation/steps.py` (the step model to reuse)

## Build
| Part | Files |
|---|---|
| flow world | `scene/worlds/flow.py`: regions, labelled parts (named only once said), flow paths with moving particles, cycles, timelines, steps (steps.py) |
| graph world | `scene/worlds/graph.py`: nodes/edges layout (deterministic), algorithm traces computed in Python (BFS/DFS, Dijkstra, sorts, stack/queue) as steps; never ahead of the teacher |
| chemistry-lite | atoms/ions/bonds as flow + graph kinds (electron transfer, bond forming); no 3D |
| continuity | entity references in the context ("the second ball", "it", "the charge"): ids + names + order; ops `set/remove/relate` on existing ids; undo stack (rev); a new topic → a new scene (the old one goes to the recap) |
| teacher | /control scene panel: entity list, editable Values (typed props → teacher source), remove entity, Undo, Redraw (one call), templates picker kept; voice "clear the scene" |
| outputs | recap slide uses the scene history; still frame in the PPTX export + archive viewer (reuse the F-014 still frame) |

## Tests
- unit: coreference context builder; undo; a step never ahead of the said words; graph traces vs reference algorithms.
- integration: recorded answers for a mixed lecture (physics → biology → CS) with ≥ 5 edits (0 tokens).
- browser: scene panel edits a value without restarting the clock; both themes.
- runtime: the same mixed lecture live (estimate ≤ 30k tokens).

## Stop point
Stop after the live mixed lecture. If the context runs long: stop after flow + graph, write the Result, and continue in a new session.

## Result
_(fill in ≤ 1 KB)_
