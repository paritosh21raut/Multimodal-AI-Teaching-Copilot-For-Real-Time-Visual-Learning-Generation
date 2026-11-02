# P1b — Semantic actions batch 1 · ADR-0015 (+ addendum) · loop: `docs/v2/LOOP.md`

_Read: this card, the P1a Result. Grep only: `story/{world,ops,compile,scene_llm}.py`, `web/story/anim/`,
`tools/{story_bench,p0_specs}.py`._

## Why (data, the P1a ranking on dev + val, 138 events, oracle 33 %)
UNKNOWN_ACTION 44 (put 5+1, jump 3, climb 3, catch 2, lift 2, give 2, push 2 + pull 1, follow 1, wake 1 …),
MOTION 24 (hold / carry 12, exit 4, detach 3, follow_path 3, throw 1, in 1), UNKNOWN_ASSET 42 (fox / lion / mouse /
goat 13, groups 9, places 9 …). Assets are P2's (environment grammar, quadruped rig, Tier-1 props): this card closes
the action + motion gaps only, so the 75 % overall target cannot be met here (honest ceiling ~55–60 %).

## Build
1. **rev stamped by the caller**: `validate(…, rev=)` takes the revision the call was made against; the model's echoed
   rev is ignored (15 of 21 refusals). The prompt no longer asks for it.
2. **New ops** (world + registry + validate + prompt, data first): `put` (obj, target, value = on|in|under|next_to),
   `give` (obj → target person), `jump` (in place, or target = onto / out of), `climb` (target needs `climbable`;
   ends on its climb anchor), `push` (value push|pull, target slides). ACTS: put / put_down → put, give, jump,
   climb, push, pull; catch / lift / take → attach hold; follow → move_to; wake → change_posture stand.
3. **Motions** (Python computes every number; the browser evaluates the curves):
   - hold: approach, reach, grip; the thing rides the hand after (walks, rides); a held box prop is hand-sized.
   - detach: a held thing falls from the hand under g to the ground; a rider steps down beside the horse; a sitter
     stands.
   - exit: walk to the nearer stage edge and leave (gone until it enters again).
   - follow_path: walk 3 m on in the facing direction (clamped to the stage); follow = behind the followed.
   - throw: projectile from the hand to the target (45°, v from the range, g); lands and rests.
   - put: approach the target, the thing goes from the hand onto / into / under / beside it.
   - give: both meet at a hand-over distance; the thing moves hand to hand.
   - jump: take-off crouch, ballistic hop (h 0.45 m → v0 = √(2gh)), land; with a target: onto / out of it.
   - climb: hands-up climb along the target to its anchor (tree: the lowest branch), stays on it.
   - push / pull: hands forward, the target (prop) slides 1.2 m away / towards, the actor steps with it.
4. **Bench**: oracle + 20b replay (old answers, rev stamped); the new ops get the LLM at the P1c re-record.
5. **Dev page** G–L (one scene per new motion group) + browser probes; one contact sheet per theme.

## Gate (yes / no)
- Oracle events dev + val ≥ 55 % (from 33), relations and continuity 100, honesty 100; no genre < 45 %.
- Every batch-1 action whose things are drawn is `executable` in the oracle (0 MOTION misses left for them).
- 20b replay (rev stamped) ≥ 26 % events, refusals ≤ 8.
- Contact sheets: the carried thing stays in the hand while walking; the thrown / dropped thing lands on the ground;
  the jump leaves and lands on the ground; the climber's hands are on the trunk; no gap / float.
- Tests green; the full suite once.

## Not in P1b
New assets (animals, places, groups: P2), the LLM re-record of the new prompt (P1c, ~180k tokens), live wiring (P1c),
the test split (scored once after the re-record).

## Stop point
Ops + motions + bench numbers + dev page; the user looks at G–L (the look test), then `test done`.

## Result
_2026-11-02, closed: re-test H K L passed (user: "everything is good now")._ rev stamped + `_renumber`; ops put / give / jump /
climb / push; motions hold, drop, dismount, exit, walk on, throw, put, hand-over, jump (v0 from g), climb, push / pull.
Look test (`tests/P1b-look-eval.md`): G I J pass; H put read as a toss, no branch; K throw unnatural; L boxes.
Round 1: set-down within reach (reach_down pose), drawn limbs + sit on them, overarm throw from the hand point with a
catch (Python aims at the catcher's hands), 8 drawn props (stone, ball, stick, basket, pot, boat, book, cart).
2301 pass + 17 browser; review 10 fixed. **Dev + val:** oracle 33.0 → **55.4** (m 46.7 h 60.2 s 59.4; rel / cont /
honesty 100) = gate met; 20b replay 23.4 → **38.8** (refusals 21 → 6). Close: optional parts (sidecar `parts`, the
tree's branch) drawn only once a line says them, then stay; no branch said = he clings to the trunk; a "branch"
entity is the tree's part, never a box. 2304 pass + 21 browser. Moved to P1c: re-record (~180k), test split.
