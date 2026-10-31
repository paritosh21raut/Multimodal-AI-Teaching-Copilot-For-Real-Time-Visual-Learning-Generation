# E3c — Bounded stage: supported actions done right, picture cards for the rest (after K1)

_Fixture-first (0 tokens), ADR-0013. Read: ADR-0013, `docs/v2/GATE-SENTENCES.md` (S rows, M rows),
`docs/contracts/stage-spec.md` §1–4. Grep, don't read whole: `src/copilot/stage/fastpath.py`, `timeline.py`
(`_drive`, sockets), `director.py` (rows, framing), `config/stage_catalog.json` (anchors), `web/stage/kit/props.js`
(swing, tree, horse, car), `web/stage/player.js`, the C1 canvas emoji card (`grep -rn "emoji" web/shared`)._

## The failure this fixes (test35)
Nouns right, relation never drawn: rider beside the horse, bird on the ground, girl beside a seatless swing, man
walking beside the car, half the tug-of-war team idle, the thrower a 5 px dot, a "walker" nobody said.

## Build
1. **Action table** `config/stage_actions.json`: the ~15 supported actions (push, pull, carry, lift, throw, kick,
   run, walk, ride, sit_on, stand_on, swing, tug, drive, read / hold). Each row: subject kinds, object kinds,
   the attach (socket on the object: saddle, seat, branch, surface, handle, rope), the clip / pose, who moves.
   Anything not in the table is **unsupported**.
2. **Attach points** in the kit + catalog: horse saddle, car driver / passenger seat (person drawn behind the window),
   swing seat on ropes (pendulum motion), tree branch (bird perches), bench / chair seat, rope grip points for
   every team member. `ride` = sit in the saddle / seat and move with it (animals and vehicles).
3. **Relation from the words**: the fast path reads the preposition / verb pair ("riding a", "sitting on the",
   "swinging on", "in the car") into the table's attach; the LLM delta may only pick table rows.
4. **Picture-card fallback**: an unsupported line → the canvas picture card (icons / emoji of the nouns, labels,
   the relation as words "boy — climbs — ladder"), logged as `[STAGE] unsupported <verb> <obj>` (the next work list).
   Never a half-acted puppet scene.
5. **Framing**: a person is ≥ 12 % of the slide height; a long projectile path uses an inset of the thrower.
6. **No invented entities**: overlays (rain relative velocity etc.) name only things that were said.
7. **Keys check** at start: a 1-token ping per Groq key; dead keys listed in the log and /control.

## Tests
- Every S row: attach contact (rider hips on the saddle ±2 px, bird feet on the branch, all tug hands on the rope);
  S10 → picture card; M rows → nothing / card.
- test35 replay: 0 slides with "person beside the thing they ride / sit on"; 0 entities not in the transcript.

## Gate (stop)
Contact sheet per theme of S1–S10 with checks printed; user marks yes / no. Pass = all S rows yes. Then the user's
live run (keys pinged first) on the full GATE-SENTENCES list.

## Result
_(≤ 1 KB)_
