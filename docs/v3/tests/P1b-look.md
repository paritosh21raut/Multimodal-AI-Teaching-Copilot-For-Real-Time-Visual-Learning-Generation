# P1b look test (no speaking: the story is not wired live until P1c)

Start: `.venv/Scripts/python -m http.server 8000` → open `http://localhost:8000/web/story/anim/dev.html` →
button **G → M**. Watch once in light, press **theme**, watch once in dark. ~3 min. Answer yes / no per line.

| # | Line on screen | Check (yes / no) |
|---|---|---|
| G | Ravi picked up an apple and walked to the tree. | He crouches, the apple goes into his hand, stays in the hand while he walks |
| H | He put the apple under the tree and climbed it. | The apple goes down under the tree; hands on the trunk going up; he ends sitting on the branch |
| I | Then he jumped off the tree. | He crouches, hops away from the trunk (not into it), lands on his feet on the ground |
| J | Meena came, and Ravi gave her the apple. | He picks the apple up, walks to Meena, the apple goes hand to hand; Meena holds it |
| K | Meena threw the apple to the boy. | Her arm swings back then forward; the apple flies in an arc and lands at the boy |
| L | The boy picked up a stone and pushed a cart. | Stone (small box) in his hand; hands forward on the cart; the cart slides, stops before Meena |
| M | He dropped the stone and walked away. | The stone falls straight down to the ground; he walks off the edge and is gone |

Also: anything floating, a gap between hand and thing, a wrong-facing turn, text overlapping? Note the letter.

Known (not this card): things without a picture are labelled boxes (stone, cart: P2 assets); two boxes on the
ground can overlap their labels.

When done, type `test done` (with your yes / no list, or "all yes").
