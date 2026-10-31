# test38 — M0 re-test evaluation (2026-10-31, by Claude)

1.2 min, 10 heard lines for 6 spoken (the user said only the script; every other wording is an STT error, and the
repeats are the user saying a failed line again). 3 slides. Understanding 10 calls × ~1.9k ≈ 19k tokens; diagram 0.

| # | Spoken | Heard | Result |
|---|---|---|---|
| 1 | Imagine a box on an inclined plane. | same | yes: one slide |
| 2 | Imagine two circles C1 and C2. | same | yes: new slide, **no** incline recap |
| 3 | Imagine another circle C3. | same | yes: same slide, title "Three circles C1, C2, C3" |
| 4 | If C1 has a pentagon inside it. | "This even has a pentagon inside it." then right | yes: pentagon in C1 (after the 2nd try) |
| 5 | A hexagon is outside C3. | 4 tries: "Zagon / The gun / Lip for the hexagon / APO Hexagon is **inside** SC3" | **no** (STT): "outside" heard as "inside" every time → hexagon drawn inside C3; "SC3" not read as C3 |
| 6 | A square has four equal sides. | "A square has 4 equal sides." | **no** (ours): a 2nd square was drawn beside C3 — a property statement is not a new part |

## Problems
1. (ours) "A square has 4 equal sides" draws a square: a sentence about a kind ("X has / is …" with no place word) is
   a fact, not a drawing.
2. (ours) Recap "Three circles…": "Gun is inside C3", "Zagon location: Inside C3", "The figure contains a pentagon
   inside the circle", "C1 contains the pentagon" — placement talk with garbled nouns passed the picture filter.
   Only "Square has 4 equal sides" belongs.
3. (STT) shape words misheard (pentagon/hexagon → Zagon, the gun) and "outside" → "inside": Whisper is not primed
   with the diagram's words (StageWords is sent for the stage only).
4. (STT) a garbled label "SC3" (extra letter in front) is not read as C3.

## Fixes (round 2, the card's last)
1. A line that states a property of a kind ("a square has …", "a pentagon is a …", no place word, not a cue) adds no part.
2. Recap: a bullet with a place word (inside / outside / contains / beside / on top) whose other words are drawn
   things, labels or unknown words is picture talk → dropped; "figure / contains / location" are placing words.
3. Prime Whisper from the open diagram: its part words, labels, and for shapes the shape family + inside / outside.
4. A label with one stray capital in front ("SC3") → C3 when C3 is open.

## Verdict
**fix**: 1–4 above; then a 3-line re-test (lines 5–6 + one recap check).
