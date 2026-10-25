# F-017 — Explainer Stage (V2, 2D) · decided 2026-10-26 · ADR-0011

**Goal.** While the teacher talks, the slide shows an accurate, animated 2D explainer scene of what was said: real
human motion (push, throw, walk, carry…), objects at true relative sizes, correct arrows, paths and numbers. The
first picture appears within ~1–2 s and the scene keeps building as the teacher goes on. **Accuracy first**: the look
gets polish rounds later (user, 2026-10-26).

## 1. Principles (non-negotiable)
1. **Compose, don't generate.** One 2D kit (chibi cast, animals, props, backdrops), one style; the engine places,
   poses, animates, annotates. No photos, emoji or generated images on the stage.
2. **The LLM says what and who; Python says where and how much.** The LLM never gives coordinates. Every shown
   number has provenance (said / computed / constant), otherwise it is a symbol and an "Illustrative" badge shows.
3. **Never wait for the network.** A 0-token draft comes first, the LLM delta refines it, and changes morph.
4. **Show less, correctly.** Only what the current sentence needs; the director dims or removes the rest.
5. The event log is the truth: replayable, undoable, testable. The UI only sends commands.

## 2. Look (locked: explainer_flat + chibi; reference `tools/stage/reference/`)
- Stage 1600 × 1000 (16:10), SVG. Sky gradient, soft hills, ground band, soft contact shadows, no outlines.
- Colour roles (fixed in every scene): applied force `#F07C1A`, friction `#E04A3A`, weight `#2F6BE0`, normal
  `#1E9E6A`, velocity / path `#8A4FE0`, water `#3B8FE0`. Ink `#33363d`, muted `#5d6672`, cards white 90 %.
  Dotted line = trajectory, dashed = construction / rest line. Words: Segoe UI; symbols: Cambria Math italic with
  subscripts. Labels ≥ 24 px at stage size. Line style is never the only cue.
- **People = chibi**: head × 1.6, limbs × 1.22, glossy eyes, brows, smile, ear and nose, round hands with a thumb,
  collar, shirt shading, waistband, white-soled shoes, hair highlight. Cast rows: sex, child, skin, hair colour and
  style (short, long, bun, ponytail, curly, bald), beard, glasses, top and sleeve, bottom (pants, skirt, shorts),
  shoes, build. Skin tones vary; a new person gets a new outfit; "the same man" keeps his.
- Animals: procedural 2D species (dog, cat, horse, cow, bird, fish now), gait synced to speed, sitting pose.
- On dark slides the stage keeps its own backdrop as a framed picture panel.

## 3. Pipeline
```
mic → Whisper (initial prompt = slide title + recent scene nouns) → sentence end
  ├─ fast path (0 tokens, < 50 ms): kit names + verb lexicon → draft ops (ghosted)
  └─ LLM delta (Groq gpt-oss-20b, cached prefix; fallback 120b; then fast path only)
→ validator (schema, ids, provenance, units, law preconditions, budgets, safety) → event log → scene graph
→ law solvers (Python) → director (layout, depth rows, framing, timing) + acting (clips, IK, sockets)
→ timeline `stage.patch` (WebSocket) → browser stage (SVG over a slide block, or the whole slide in Imagine Mode)
```
Contract: `docs/contracts/stage-spec.md`.

## 4. Picture supply
- **Motion**: `motion.json`, 87 CC0 clips (Quaternius UAL1+2) baked to 2D joints (24 fps, 1 m tall, facing +X, feet
  on the ground). Each clip has a table row (`config/stage_clips.json`): loop, stride speed, event frames (contact,
  release, footstrike, apex), seat height, hand heights.
- **Kit** (`web/stage/kit/`, rows in `config/stage_catalog.json`): props with `size_m`, anchors / sockets (top,
  front face, handle, seat, spout…) and states (bulb on, beaker fill, switch closed); backdrops (outdoor, park,
  street, classroom, lab bench, room, night, space, pool / underwater, soil cutaway, river top view, sky); species.
  Target: about 60 props in E1, about 150 by E3, more from the logged misses.
- **Lookup ladder** (per noun, cached): 1 exact / synonym → 2 MiniLM nearest above a threshold, with a chip
  showing the said word → 3 the LLM's `near` hint → 4 generic kit shape (rod, ball, box, cylinder, coil, cloud,
  plate, wedge, spring, wire, lens, planet, cell) → 5 a flat icon recoloured to the palette → 6 a labelled rounded
  box. Never a wrong picture. Misses go to `data/assets/stage/misses.jsonl`.

## 5. Views and framing (2D)
`side` (default), `top` (river, orbit, map, table top), `cutaway` (soil, pot, beaker inside, body part), `split`
(two synced panes on one scale, e.g. Moon | Mars), `inset from:<id>` ("seen from the man" card), `diagram` panel.
Depth: **near row** (scale 1) and **far row** (about 0.6, drawn behind, e.g. watchers across the road). Camera =
2D pan + zoom with easing (establish → act → focus); no camera move during a key moment.

## 6. Acting (verb → clip + IK; closed list in the contract)
walk / jog / run (playback rate = solver speed ÷ stride speed) · stand, talk, phone, fold_arms, nod, call, point ·
push (hands IK on the near face for the force interval), pull (push mirrored, hands on rope / handle) · throw (object
on hand_r until the release frame = solver t0) · carry, pick_up, put_down · sit (seat height from the clip) · jump
(height from the solver) · swim, drive, climb, crouch, kneel, roll · water, plant, chop, eat / drink, dance. Unknown
verb → nearest listed (LLM picks), else move + arrow. Objects move by solvers or tweens.

## 7. Director rules
Ground line about 75 % of the height. Motion goes left → right. The agent stands on the side the action comes from.
Frame the entities of the current sentence (thirds, 6 % margins). Slide text boxes are no-go zones. Entrances are
staggered about 100 ms; arrows appear after motion starts; labels don't overlap (nudge order). Things not mentioned
lately are dimmed; at most 12 visible entities. Scale: true relative size inside an interacting group; compressed
across groups with a "Not to scale" badge; enlarged details (seed, particles) say so.

## 8. Education layer (Python owns the numbers)
Law modules: uniform / accelerated motion, projectile, sliding friction, relative motion (frames, "seen from"),
free-fall compare (Moon / Mars / Earth), moments (lever / seesaw), pendulum energy, buoyancy, apparent weight,
collision 1-D, orbit, wave on a string, reflection / echo, shadows / rays, refraction, static fields. Each has
roles, required givens, and outputs with provenance. Modes: **quantitative** (all givens said), **qualitative**
(shape only, symbols, badge), **illustrative** (the teacher's words only). Diagram recipes (our code): axes + curve,
Riemann strips, vectors, free-body, field lines, particles, wavefronts, rays, atom, circuit, cycles (water,
photosynthesis), Moon phases. The 21 S0–S4 templates become recipes / law modules; teacher-picked templates still
work.

## 9. Targets (E5 measures them)
| Metric | Target |
|---|---|
| sentence end → first pixel (draft) | p50 ≤ 1.0 s, p95 ≤ 2.0 s |
| full scene (LLM delta) | p95 ≤ 3.0 s |
| unsupported numbers on screen | 0 |
| scene correctness (entities, relations, actions, physics) | ≥ 85 % of visual sentences, 2 annotators |
| contacts | hands within 2 px of their target; planted foot drift ≤ 1 cm per step |
| look | blind pairwise vs the C1 canvas: stage preferred ≥ 80 % |
| tokens | ≤ 750 counted per call; ≤ 4k per minute in Imagine Mode |
| stability | < 1 visible retraction per minute; ≥ 50 fps with Whisper running |

## 10. Keep / drop / later
- Keep: speech pipeline, core, LLMRouter, validator pattern, solvers, Imagine Mode, sim mode + recap, safety,
  /control, tests, the 21 templates. Drop on the stage: photos, emoji, Fluent 3D, SD-Turbo, puppets, 3D.
- Not possible live now → closest: any verb → ~35 clip verbs + IK; fluids with numbers → stylised particles;
  3D turnarounds → side / top / cutaway views.
- Later: polish rounds (people, props, animals); toon3d people option; more clips (paid UAL tier); paid tokens.
- **V3 / V4:** V3 Story = same stage + `beat` / `shot` timeline, cast registry, sets, captions only from said
  words, `personify`. V4 = same graph; only STT, the fast path and captions change per language.
