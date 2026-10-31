# F-019 — Live Concept Simulator (ADR-0014)

The teacher talks; concept lines become one live, accurate simulation per concept that **grows with every line**:
the K1 composed diagram (S0–S4 look) + quantities said + a domain solver's results (forces, accelerations, motion).
No template per scene. Laptop target: 4 GB GPU for STT only; solvers, layout and rendering on CPU; Groq free tier.

## 1. Pipeline (per heard line)
```
STT line → route (K1 route.py: diagram or not) → open scene?  → fast path (0 tokens) ─┐
                                                              → LLM extract (M3) ─────┤→ validate → scene log
scene graph (fold) → domain pick (from relations) → solver(s) → results → layout + patch → player
```
- The **scene** = the K1 `DiagramLog` graph extended with **quantities** and **asks** (what the teacher wants shown).
- A follow-up line ("the weight of the box is 5 kg", "now make it 45 degrees", "another circle C3") edits the open
  scene; it never opens a new slide unless it is a new concept cue (`_same_diagram` + the M0 continuity rules).

## 2. Quantities (new op `qty`)
`{"op":"qty","on":"<part id>|<relation id>","sym":"m|F|mu|mu_s|theta|k|r|v|u|h|L|q|R|V|…","v":5,"u":"kg",
  "q":"<exact words said>","dir":"left|right|up|down|along|<deg>"?}`
- Value + unit parsed by `copilot.simulation.values.heard()` (spoken numbers, "5kg", "fifty newtons"); `q` must
  appear in the recent lines (stage `quoted_numbers` rule). "weight 5 kg" = mass 5 kg (said unit wins; the slide
  shows "m = 5 kg (said: weight)").
- Attachment: the noun in the line ("of the box", "on the bottom block", "of C1"); a pronoun → the last said part;
  no noun + one candidate → that one; else asked, not guessed (logged `[SIM] value unattached`).
- Restated → replaces (latest wins), the old value kept in the log. Units converted by Python only.

## 3. Domains and solvers (`src/copilot/diagram/solvers/`)
Each solver: `applies(graph) -> bool`, `solve(graph) -> Results`; pure Python, deterministic, ≤ 20 ms.
`Results` = list of `Value(sym, v, u, on, src="computed", from=[syms], eq="…")` + `Force` arrows + `Track`s.

| Domain (card) | Covers | Method |
|---|---|---|
| contact mechanics (M1) | block on floor / incline, stacked blocks, applied forces, friction (static / kinetic), normal, weight, rope over a pulley (Atwood, table + hanging), spring + mass | Newton per body along each contact; friction regimes: enumerate stick / slip per contact (≤ 2^n, n ≤ 4), keep the consistent one; springs → SHM |
| motion (M5) | uniform / accelerated, free fall, projectile, relative velocity (rain–umbrella, two cars, boat–river), circular | closed forms (reuse `stage/laws/motion.py`, `relative.py`, `projectile.py`) |
| later | circuits (MNA, old K2), ray optics, fields, atoms / chemistry tables (old K3–K4) | one card each |

Missing input → the solver returns **symbols** for what it cannot compute (direction still shown).
Not covered → the diagram shows "not simulated" (badge), never a wrong number.

## 4. Display
- Forces: arrows from the contact / centre, colour per kind (weight, normal, friction, applied, tension, spring),
  labelled `mg = 49 N` (computed) / `F = 5 N` (said) / `f` (symbol). Free-body view toggle per body.
- Values panel (right): said values with their quote, computed values with the equation (`a = (F − f)/m`).
- Motion: the body moves by the solver's x(t) (seamless loop / restart), slipping vs sticking visible.
- Look: K1 parts + S0–S4 arrows / panels (reuse `web/sims/` styles). Both themes.

## 5. Continuity and slides (M0)
- One slide per concept; a repeated cue (Whisper repeat) never adds a slide.
- "another / a third / one more X" adds X to the open scene; "X inside / on Y" relates to the open scene's Y.
- Recap = only the lines of its own scene; never an LLM-added link; no number changed.
- Understanding LLM output: any number not in the transcript window is dropped (guard in code, not prompt).

## 6. LLM extraction (M3)
One Groq call per concept / value line not fully parsed by the fast path, ≤ 1.2k tokens; output = ops of
§2 + K1 ops (closed vocabulary); validator as K1 + quantity rules. Fast path stays first (0 tokens).

## 7. Tests and gates
- Fixtures: `tests/fixtures/diagram/<card>_*.json` (lines → expected scene, values, results within 1e-6).
- Solver unit tests against hand-worked textbook answers (stated in each test).
- Gate = contact sheet per theme with yes/no checks + the live loop test (`LOOP.md`).

## 8. Not in F-019
People acting (picture card instead), stories, imagination canvas, 3D, image / video generation.
