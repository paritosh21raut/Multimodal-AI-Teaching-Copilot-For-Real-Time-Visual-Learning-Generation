# K1 — Concept Diagram core (F-018 session 1, after the test35 scope reset)

_Fixture-first (0 tokens). Why this is next: ADR-0013 (test35 verdict). Read: `docs/v2/F-018-concept-diagrams.md`,
ADR-0012, ADR-0013, `docs/v2/GATE-SENTENCES.md` (rows D1–D5, D9–D10, M1–M2), `docs/contracts/stage-spec.md` §1, §6–8
(reuse the op / validator / event-log pattern). Grep, don't read whole: `web/sims/draw.js`, `bohr_atom.js`,
`incline.js`, `orbit.js`, `neutralisation.js` (the look to match); `web/stage/player.js` (patch playing);
`src/copilot/presentation/stage.py` (`same_scene`, `start`, `_publish`); `src/copilot/scene/detector.py` (cue);
`verify_results/test35/transcript.txt` + `terminal_log.txt` (grep `[SCENE]`, `[SIM]`, `UNDERSTAND`)._

## The failure this fixes (test35)
Incline → box on the grass beside a triangle; beaker + HCl → a man walking, a text tile, a tiny beaker; atom → an
app icon; solar system → a bullet slide "Imagine our solar system"; two circles C1, C2 → nothing. Concept lines must
become clean diagrams: no person, no sky / grass, things IN / ON each other, labelled, S0–S4 look.

## Build
1. **Contract** `docs/contracts/diagram-spec.md` (≤ 6 KB): ops `part group wire contain solution place process given
   show mode`, ids, ports / anchors per part kind (surface, inside, top, end), relations `on in hang_from orbit
   around connect`, the `diagram.patch` (parts with xform, wires as polylines, labels, overlays, tracks),
   provenance rules (as stage-spec §6).
2. **Part library v1** `config/diagram_parts.json` + `web/diagram/parts/*.js`: ~30 parts for the gate rows first —
   block, incline (surface anchor + angle), floor, spring, mass, pulley; beaker, flask, liquid (fill level, label),
   pour stream, stirrer, burner; nucleus, shell, electron; sun, planet (8, true order, relative size not to scale),
   orbit; circle / shape with a label; bar magnet, compass; cell, resistor, bulb, switch, wire node (K2 uses them).
   True aspect, anchors, label anchors; light + dark tokens; the S0–S4 line weights. No sky, no grass.
3. **Python** `src/copilot/diagram/`: `ops.py` (pydantic), `validate.py` (closed kinds, anchors exist, counts,
   quotes), `graph.py` (fold), `layout.py` (relations solved first: ON = bottom on the surface anchor along the
   slope, IN = inside the container's fill box, HANG_FROM, ORBIT = rings around the centre; then a grid for the
   rest; label boxes never overlap parts), `patch.py`, `fastpath.py` (deterministic draft for the gate lines: nouns
   + the preposition → ops; "solar system" / "atom" expand to their parts; element / shell table for atoms).
4. **Routing** (`stage.py` + detector): a line whose drawable nouns are all concept parts → diagram mode, **also
   when it says "imagine" / "you"** ("Imagine in a beaker you have HCl" = diagram, "you" is not drawn). Person /
   animal nouns with an action → stage. A concept line never falls to a bullet slide. Follow-up lines ("and you're
   adding water to it") stay on the open diagram. /control "Diagram | Scene" switch (a command, UI sends it).
5. **Player** `web/diagram/player.js`: draws a `diagram.patch` full slide under the title; tweens on updates;
   seamless loops (orbit, electron spin, pour, stir, current dots).
6. **Fixtures** `tests/fixtures/diagram/k1_*.json`: op scripts for D1–D5, D9, D10 + 5 more (cell + bulb + switch,
   2 resistors in parallel, flask on a burner, pulley + 2 blocks, a labelled unknown part).

## Tests
- Validator: unknown kinds / anchors / ids refused with reasons; counts kept exactly; no number without a quote.
- Layout: ON = contact on the surface (≤ 1 px gap, along the slope); IN = inside the container box; no overlaps;
  labels clear of parts (bounding boxes); planets in order.
- Routing: all GATE-SENTENCES D and S rows + M rows → diagram / stage / nothing as listed; the test35 transcript
  replayed: 5 concept lines → 5 diagrams, 0 people on them.
- Browser: the 12 fixtures render in both themes without errors.

## Gate (stop)
Contact sheet per theme: part library grid + the 12 diagrams, each with its GATE-SENTENCES checks printed under it.
The user marks yes / no. Pass = D1–D5, D9, D10 all yes. Misses → look list for K2.

## Result
2026-10-27, 0 tokens. Built `src/copilot/diagram/` (parts table, ops, validator, event log, fast path, route,
layout, patch), `web/diagram/` player + 30 parts, Diagram|Scene switch, diagram undo/freeze. 12 fixtures (D1–D5,
D9, D10, X1–X5) reproduced by the fast path; test35 replay: 5 concept lines -> 5 diagrams, 0 people, people lines
stay on the stage. Review: 12 findings fixed (measure≠count, everyday words, abstract-noun boxes, validator
holes/KeyError, compass, _switch, same-noun cue, freeze, passive pour, hang target, circuits said later). Unit + browser tested: full 1959 pass, diagram/stage browser 28 pass.
Contract change (ADR-0013): "Imagine an inclined plane." is now a diagram cue (test_scene, test34 row 33).
Sheets: `artifacts/diagram/sheet_k1_{light,dark}.png` — **gate: user marks the yes/no checks.**
Open: LLM delta for diagrams (K5); current dots (K2); focus colour; not live-run.
