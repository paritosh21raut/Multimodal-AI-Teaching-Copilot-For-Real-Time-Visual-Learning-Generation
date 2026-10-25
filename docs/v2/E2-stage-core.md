# E2 — Stage core: event log, validator, laws, director, acting (0 tokens)

_Session 2 of F-017 (2D). Everything is driven by scripted op files (fixtures), no LLM. Needs E1's stage + catalog._

## Read first
- `docs/contracts/stage-spec.md` (all).
- `docs/v2/F-017-explainer-stage.md` §5–8.
- E1 card Result.
- `src/copilot/scene/validate.py` + `ops.py`: grep `Checked`, `apply`. Reuse the pattern; don't copy the canvas code.
- `src/copilot/scene/worlds/motion.py`, `worlds/relative.py`: solvers to wrap.
- `web/stage/player.js` (the patch it plays).

## Build
1. **`src/copilot/stage/`:**
   - `ops.py`: pydantic models of contract §1 and the closed lists §3–5.
   - `validate.py`: contract §6, incl. the quote / unit check with `pint` (add the dependency).
   - `log.py`: event log, fold → graph, undo.
   - `graph.py`.
2. **`laws/`:** `uniform_motion`, `accelerated_motion`, `projectile`, `sliding_friction`, `relative_motion`,
   `free_fall_compare`, `moments`, `pendulum_energy`, `buoyancy`, `apparent_weight`.
   - Wrap existing solvers where they exist.
   - Outputs carry provenance.
   - Constants come from `config/constants.toml`, with source notes.
3. **`director.py` (2D):**
   - **Layout and staging:** ground line; agent side; left → right motion; near / far rows (`behind` → far, scale
     ≈ 0.6); groups at true relative size; compressed across groups with a badge.
   - **Framing:** fit the current sentence's entities; slide no-go boxes; entrance stagger.
   - **Labels:** placement with a nudge order (no overlap with figures or other labels); dimming; ≤ 12 entities.
4. **`acting.py`:**
   - verb → clip row (`config/stage_clips.json`); playback rate = solver speed ÷ stride speed.
   - **Time-warp** clip events to solver events (throw release = t0; push contact = force interval; jump apex =
     solver apex).
   - **IK targets** from prop anchors (push face, rope, handle, swing rope, seesaw handle).
   - **Sockets:** holding, carry, on top, sitting on.
   - **Mirror** for pull.
   - Animals: gait speed.
5. **`timeline.py`:** graph + solver output + director + acting → `stage.patch` (contract §8) and patch diffs.
6. **Fixtures** `tests/fixtures/stage/ops/*.jsonl` (op scripts, each with expected key facts):
   1. a man pushes a box → harder → stops;
   2. throw a book (symbols), then "at 10 m/s at 30°";
   3. Moon vs Mars jump (split);
   4. rain on a walking man + "seen from the man";
   5. a car speeds up from rest (strobe marks);
   6. a woman carries a box onto a table;
   7. a ball rolls off a desk;
   8. seesaw balance (father + daughter);
   9. swing energy;
   10. tug of war (left team wins);
   11. a man walks his dog in the park;
   12. a lift speeding up (N > mg).
7. **Replay** `tools/stage/replay.py`: op script → patches → `tools/stage/shoot.py` sheet. Deterministic.
   E1's hand-made patches are retired once their scenes come from ops.

## Tests
- **Unit:**
  - Validator rejects bad id, unquoted number, wrong unit, unknown verb and missing precondition.
  - Every law matches its closed form.
  - Provenance: every overlay number has a record; the illustrative flag is set when defaults are used.
  - Fold / undo.
  - Director: no entity outside the stage, no label overlap (bounding boxes), far row scaled and behind.
- **Acting:**
  - Release frame = solver t0 (± 1 frame).
  - Hands within 2 px of the push face during the force interval.
  - Foot drift ≤ 1 cm per step.
  - Seat contact for sitters.
- **Browser:** every fixture replays with no console errors.

## Gate (stop)
A contact sheet of the 12 fixtures at key frames, side by side with the E1 reference where one exists. The user
judges physics, readability and look → the look list goes to P-round 1.

## Result
_(≤ 1 KB)_
