# M2–M5 — outline cards (refined into full cards at the start of each session) · ADR-0014 · `LOOP.md`

Each session first turns its section into a full card `docs/v2/Mx-<name>.md` (≤ 5 KB) using the previous card's
Result and its live-test EVAL, then runs the loop.

## M2 — Look and motion polish
- Free-body toggle per body (/control), arrow overlap avoidance, value panel layout, slip / stick motion loop,
  re-solve morph when a value changes (old arrow → new length), both themes, projector contrast.
- Leftovers from M1's EVAL. Gate: sheet + live test (the M1 lines re-spoken + 5 new wordings).

## M3 — LLM scene extraction (Groq, bounded)
- Prompt (cached system part) → ops of `diagram-spec.md` + `qty` (closed vocabulary), validator unchanged;
  called only when the fast path leaves nouns / numbers of a concept line unparsed; ≤ 1.2k tokens per call,
  keys rotated, dead keys pinged at start. Paraphrase fixture set (30 lines, from M0–M2 tests + new wordings)
  must give the same scene graphs as the fast-path fixtures (replay via recorded responses, 0 tokens in CI).
- Gate: paraphrase replay ≥ 90 % same scene; live test with free wording (12 lines); tokens reported.

## M4 — Live mechanics lecture run
- A 10-min mechanics lecture script (incline → friction → stacked blocks → pulley → spring) spoken by the user;
  latency budget: cue → diagram ≤ 1.5 s, value → re-solved ≤ 1 s (fast path), ≤ 3 s (LLM).
- Fix round on its EVAL. Gate: all must-pass lines yes; 0 wrong numbers; ≤ 1 slide per concept.

## M5 — Motion and relative velocity solver
- `solvers/motion.py`: uniform / accelerated, free fall, projectile (range, H, T), relative velocity (rain–
  umbrella angle, two cars, boat–river), circular (v, a_c, T). Reuse `stage/laws/motion.py`, `relative.py`,
  `simulation/templates/projectile.py`. Diagram parts: ball, car, man (simple K1 figure, no stage puppet),
  rain field, river; tracks from x(t), velocity triangle overlay.
- Gate: sheet + live test (12–15 lines incl. test36's "throw a ball at 10 m/s" and "two cars 50 / 60 km/h").

## After M5 (not planned in detail)
Circuits (old K2, MNA), ray optics, fields, atoms / chemistry (old K3–K4); then Story (V3); then Canvas.
People scenes: picture card only until then.
