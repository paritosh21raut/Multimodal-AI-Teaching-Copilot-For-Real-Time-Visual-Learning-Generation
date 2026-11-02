# P1c live test — the story animates as you speak (~6 min, ≈ 25k Groq tokens)

Start: `.venv/Scripts/python tools/eval_test.py run --note "P1c live"` (Enter to start, `q` + Enter to end).
Speak each line as written, pause ~4 s after each (watch the projector). Yes / no per check.

| # | Say | Check (yes / no) |
|---|---|---|
| 1 | Let me tell you the story of Ravi. | Story slide opens; Ravi (name tag) stands on the stage |
| 2 | Ravi was sitting under an apple tree. | A tree with apples; Ravi sits under it |
| 3 | An apple fell on his head. | One apple drops onto his head, bounces, lands; he reacts |
| 4 | Ravi picked up the apple and walked to the village. | He picks it up; it stays in his hand while he walks; houses appear |
| 5 | There he met his sister Meena. | Meena (name tag, her own look) comes in |
| 6 | Ravi gave the apple to Meena. | They meet; the apple goes hand to hand; Meena holds it |
| 7 | Meena said, thank you, brother. | Bubble "thank you, brother" at Meena; it stays up after |
| 8 | Then Meena threw the apple to Ravi. | Arm swings; the apple arcs to Ravi's hands |
| 9 | Ravi put the apple in a basket. | A basket; the apple goes into it |
| 10 | Okay class, look at the board. | NOT a story line: nothing new moves |
| 11 | Ravi climbed the apple tree. | He walks to the tree; hands on the trunk going up |
| 12 | Then he jumped off the tree. | Crouch, hop away from the trunk, lands on his feet |
| 13 | An old man rode his horse to the village. | A stooped man on a horse rides towards the houses |
| 14 | Can everyone see the screen? | NOT a story line: nothing new moves |
| 15 | Then he jumped off the tree. | Repeat of 12: no new motion |
| 16 | Meena picked up a stone and pushed a cart. | Stone in her hand; hands on the cart; it slides |
| 17 | And that is the end of the story. | The story ends; slides come back (recap) |

Overall: every shot starts within ~2.5 s of the line's end (p90 ≤ 4 s); nothing moves that you did not say.
