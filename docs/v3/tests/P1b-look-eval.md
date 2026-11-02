# P1b look test — evaluation (user, 2026-11-02)

| # | User | Verdict | Cause (ours) |
|---|---|---|---|
| G walk, pick up, carry | good / fine enough | yes | — |
| H put under the tree | "throws the ball towards the tree, not natural" | **no** | the put spot is the trunk centre, ~1 m away; the apple tweens there from the hand with a lift = it reads as a throw |
| H climb | fine | yes | — |
| H sit on the branch | "no branch, sits on a bush, no logic" | **no** | the tree has no drawn branch; the sit pose is the ground sit (legs straight out) inside the canopy |
| I jump down | good | yes | — |
| J give | good | yes | — |
| K throw to the boy | "not natural or good" | **no** | released from the waist hand while the arm whips up (the apple leaves the wrong point); lands at the boy's feet, nobody catches; 45° lob; short wind-up |
| L / M stone, cart | "no logo, just a white box" | **no** | no drawn props (stone, cart): the fallback box |

## Fixes (round 1)
1. **Put = set down, not toss**: the spot is on the actor's side within reach (under the tree: in the shade span next to
   him); he walks up, crouches, the hand carries it down to the spot, opens, he stands (no arc, no hand-to-far tween).
2. **Branch**: tree.json gets a drawn branch (from the trunk to the anchor); the climber sits ON it with legs hanging
   (the saddle seat pose), pelvis on the branch line.
3. **Throw**: wind-up behind the head, step forward, release at the forward hand point (Python and rig share the
   point); a person target **catches**: hands up, the arc ends in the catcher's hands (Python aims at that point),
   then it is held; a lower, faster arc (35°); no target / a place: lands and rolls a little.
4. **First drawn props** (pulled from P2 Tier-1, user feedback): stone, cart (wheels), ball, stick, basket, pot /
   bucket, boat, book — line-art shapes with sidecars + affordances; a noun with no prop stays a labelled box.

## Round 1 built (re-test only H, K, L)
Dev page (same steps), button **G → M**; watch H, K, L in light and dark:
| # | Check (yes / no) |
|---|---|
| H | He walks right up, bends down, his hand carries the apple to the ground beside him (no toss); a brown limb on each side of the trunk; he ends sitting ON the limb, legs hanging |
| K | Meena steps forward, winds up behind her head, throws overarm; the boy raises his hands and catches it; he holds it after |
| L | A grey stone in his hand; a wooden cart with wheels; the wheels turn as he pushes |

## Re-test (user): all pass. One change asked: the plain tree unless the branch is said ("climbed the tree and sat on
the branch" shows limbs), and the same rule for other things' parts → sidecar `parts`, drawn only once said.
