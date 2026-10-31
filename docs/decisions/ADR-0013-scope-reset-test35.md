# ADR-0013 — Scope reset after test35: diagrams first, a bounded stage, honest fallbacks, picture-true gates

Date 2026-10-26 · Status: **accepted** (user: "do the necessary changes") · Amends ADR-0011, ADR-0012. **Order superseded by ADR-0014 (2026-10-31): M0–M5 live concept simulator first; E3c parked.**

## Context
test35 (7.6 min, 35 lines, 14 slides) after E3b: the scene count was right, the pictures were wrong. Every failed
slide had the right nouns standing in a row on grass; the relation was never drawn (riding a horse → squatting
beside it; box beside the incline; bird on the ground beside the tree; girl beside a seatless swing; man walking
beside the car; HCl as a text tile next to a tiny beaker). Concept topics (incline, beaker, atom, solar system,
two circles) went to the people stage or to a bullet slide. 25 connect timeouts and 2 dead keys meant the LLM
corrections often never arrived. E3b was gated on slide counts and replay tests, not on "does the picture match
the sentence", so it passed while the pictures failed.

## Decision
1. **Diagrams first.** F-018 K1 is next. Concept lines ("Imagine an atom", "a box on an incline", "you have HCl in
   a beaker") route to diagram mode even when the line says "you" / "imagine"; the stage never draws them.
2. **The stage is bounded.** It supports a fixed action list (~15: push, pull, carry, lift, throw, kick, run, walk,
   ride, sit on, stand on, swing, tug, drive, read / hold), each with its attach points (seat, saddle, branch, surface,
   handle), pose and tests. No new open-ended verb handling.
3. **Honest fallback.** A line the stage does not support (unknown verb or relation, unknown noun) shows a
   **picture card**: icons / emoji of the nouns with labels and the relation as words ("bird — on — tree"), never
   a half-acted puppet scene.
4. **Picture-true gates.** Every stage / diagram gate runs `docs/v2/GATE-SENTENCES.md`: each sentence has yes/no
   checks on the picture (e.g. "the box touches the incline surface"); the user marks them. Slide counts and replay
   tests are necessary, not sufficient.
5. **Before any live run:** all Groq keys answer (a 1-token ping per key at start, dead keys listed), network OK.

## Consequences
- Order: **K1 → E3c (bounded stage + fallback) → K2–K5 → E4 → E5.**
- The "anything the teacher says, acted" goal is dropped for people scenes; it stays for concept diagrams within
  their domains (part grammar). Unsupported lines are visible as picture cards and logged as the next work list.
