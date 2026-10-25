# E1 — Stage renderer, chibi cast, kit, motion pack (0 tokens)

_Session 1 of F-017 (2D). No LLM. Port the approved samples into clean, tested modules. Accuracy first._

## Read first (only these)
- `docs/v2/F-017-explainer-stage.md` §2, §4, §5, §7.
- `docs/contracts/stage-spec.md` §8–9.
- `tools/stage/reference/README.md`, then grep the files it names (don't read the 30–40 KB files whole).
- `web/scene/scene.js`: grep `SceneStage`, `clockOf`, to see how a scene block mounts and keeps its clock.
- `web/display/app.js`: grep where block kinds are switched.
- `tests/e2e/test_scene_browser.py`, for the browser test pattern.
- `src/copilot/scene/sizes.py`, the real-size table.

## Build
1. **Motion pack.**
   - Move `tools/imggen/bake_motion.py` + reference `rig.js` / `bake.html` to `tools/stage/bake_motion.py` (reads
     `data/assets/stage/src/ual{1,2}.zip`, CC0).
   - Output `web/stage/data/motion.json`, rounded to 3 decimals (committed, ≤ 1.6 MB).
   - Also output `config/stage_clips.json`: per clip loop, stride speed (the reference `natSpeed`), event frames
     (contact for push, release for throw, footstrikes, apex for jump, by scanning joints like the reference
     throw), seat height (sit clips), hand heights; verb list per clip (F-017 §6).
2. **`web/stage/` ES modules** (no build step; preact only where a block mounts):
   - `style.js`: explainer tokens + colour roles.
   - `svg.js`: helpers.
   - `motion.js`: load, `sample(clip, t, loop, mirror)`, stride speed.
   - `people.js`: the chibi figure from `people2.js` `shaped(..., {head: 1.6, limb: 1.22, chibi: 1})`, cast, IK,
     sockets `hand_r`, `hand_l`, `lap`, `head_top`, `back`.
   - `animals.js`: the reference species incl. sitting.
   - `kit/`: props + backdrops registry keyed by catalog id.
   - `overlays.js`: arrow, dotted path, label (symbol with subscripts), dimension line, card, badge, clock, energy
     bars.
   - `stage.js`: mount, 1600×1000 viewBox, frame pan / zoom ease, rAF loop, resize.
   - `player.js`: applies `stage.patch` and plays tracks: path, clip with rate / mirror / t_offset, ik, socket,
     tween.
   - **Rendering:** one persistent `<g>` per entity; per frame only changed `d` / `transform` attributes change. No
     full innerHTML rebuild like the reference.
3. **Catalog** `config/stage_catalog.json`, rows as in contract §9:
   - About 60 props, all with `size_m` from `sizes.py` or a new row:
     - from the reference: crate, ball, table, tree, car, beaker, bench, seesaw, swing, watering can, pot +
       plant, lamp post, rope, post, cliff, board, desk, chair, bulb, cell, switch, wire, lift, scale;
     - new: book, bag, bottle, cup, phone, laptop, door, bicycle, bus, boat, ladder, ramp, spring,
       pulley, magnet, compass, thermometer, flask, test tube, burner, sun, moon, planet, cloud, rock, house.
   - 10 backdrops: outdoor, park, street, classroom, lab bench, room, night, space, pool, soil cutaway.
   - The 6 species.
   - A browser test checks that every catalog id has a draw function and vice versa.
4. **Cast** `config/stage_cast.json`: 12 people (6 m, 6 f; children, elders; varied skin tones, hair, outfits, from
   the reference CAST + 2 more).
5. **Accuracy fixes** found in the samples:
   - Planted feet must not slide: walking playback rate = speed ÷ stride speed.
   - Hands exactly on targets after IK.
   - Mirrored push for pull: lean back.
   - Sitting seat heights from the clip.
   - Child proportions.
   - Shoes not chunky.
   - Labels never overlap a figure (nudge).
6. **Patch fixtures** `tests/fixtures/stage/patches/*.json`:
   - 8 reference scenes rebuilt as `stage.patch` JSON: push, throw, carry onto table, tug of war, seesaw, swing,
     rain on a walking man, Moon | Mars jump.
   - Made by `tools/stage/make_patches.py` with the closed forms from the reference, the same numbers as the
     samples.
   - Mark these hand-made patches; E2 makes them from ops.
7. **Shoot tool** `tools/stage/shoot.py`: patch(es) → contact sheet PNG (Playwright + Edge, like
   `tools/imggen/shoot_v2look2d.py`; local server on a free port).

## Tests
- **pytest:** catalog / cast / clip-table schema (ids unique, size_m > 0, clips exist in motion.json, event frames
  in range); `make_patches.py` is deterministic.
- **Browser** (`tests/e2e/test_stage_browser.py`):
  - The stage mounts and plays all 8 patches with no console errors.
  - Every catalog id draws.
  - Hands within 2 px of their IK targets.
  - Planted foot drift ≤ 1 cm per step at stride speed.
  - Throw release frame = path t0 (± 1 frame).
  - Average frame time with 6 people + 30 props ≤ 8 ms (measure once with Whisper running; report it).

## Gate (stop)
Sheets (`artifacts/stage/`):
1. 12 cast people × 6 poses (walk, push, throw, carry, sit, jump);
2. all props in a grid at true relative size with a 1 m bar;
3. 10 backdrops;
4. the 8 patch scenes at key frames.

The user judges accuracy and the look; a ≤ 10-item look list goes to the P-round.

## Result
2026-10-26. Built (unit + browser tested):
- motion pack: 87 clips, 1.5 MB
- clip table: stride, events, seat and hand heights, foot lock
- web/stage modules
- 61 props, 10 backdrops, 6 species, 12 cast
- 8 patches from make_patches.py (reachable grips)
- shoot.py and 4 gate sheets

Tests: 8 pytest, 6 browser.
- IK error 0 px on push, tug, seesaw and swing.
- No planted-foot drift above 1 cm on walk, push, carry or the winning tug team.
- Throw release continuous.
- About 1 ms per frame with 6 people + 30 props with medium.en transcribing on CUDA (short run).

Review fixes:
- camera keyframes wrap with the period
- sockets sorted by t0
- whole-cycle periods
- tug feet locked
- drift test must measure stances

Open for E2:
- the place() cycle guard can cache a pose aimed at the un-socketed spot (IK on a held object)
- a path that starts before socket t1 jumps at release
- the losing tug team skids (intended); the tug loop reset jumps
- config from ../../config (needs a server route)
