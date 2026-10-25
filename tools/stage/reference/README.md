# Look reference (frozen samples, 2026-10-26)

The 2D samples the user approved (explainer_flat look, chibi people). E1 ports them into `web/stage/` as clean
modules; these files are reference only and are not served by the app.

| File | What to take from it |
|---|---|
| `2d.html` | motion sampling (`sample`, `natSpeed`, `clipMax`), `view`, explainer theme tokens, overlays (arrow, label, words, badge, card), props (crate, ball, table, tree, car), round-1 scenes |
| `people2.js` | chibi person (`shaped` with `{head: 1.6, limb: 1.22, chibi: 1}`), cast table, two-bone IK, procedural animals (dog, cat, horse, cow, bird, fish; sitting pose) |
| `scenes2.js`, `scenes3.js` | 32 example scenes (park, tug, classroom, boat, refraction, lift, water cycle, photosynthesis, circuit, orbit, seesaw, swing, watering, germination, speed-up, echo, shadow, rope wave, floating, states, magnet, Moon phases) |
| `motion.json` | 87 CC0 clips (Quaternius UAL1+2) baked to 2D joints: 24 fps, 1 m tall, facing +X, feet on the ground |
| (moved) `rig.js`, `bake.html` | now `tools/stage/rig.js`, `tools/stage/bake.html`, run by `tools/stage/bake_motion.py` (sources in `data/assets/stage/src/ual{1,2}.zip`, CC0) |
| `toon3d.js` | not chosen (3D body rendered into 2D); kept for a possible later "detailed people" option |

To view: copy this folder to `artifacts/v2look/` (with `vendor/` three r160 and `assets/` for toon3d only) and serve
the repo root; `2d.html?theme=explainer&fig=chibi`.
