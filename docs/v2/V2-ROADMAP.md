# V2 roadmap — Live Concept Simulator (F-019) · 2026-10-31

Decision ADR-0014 (after live test36) · spec `F-019-concept-simulator.md` · diagram contract
`docs/contracts/diagram-spec.md` · work method **`LOOP.md`** (build → fixture gate → live test script → the user
speaks it → Claude evaluates `verify_results/testN` → fix → next card; the user types `next` / `test done` /
`fix` / `ok`). Order: **Concept Simulator → Story (V3) → Canvas of Imagination.** One card = one session.

| # | Card | Builds | Gate | Status |
|---|---|---|---|---|
| E0–E3b | F-017 cards (`E1`…`E3b`) | 2D stage: renderer, core, live language, test34 fixes | — | done; people stage now **parked** |
| K1 | `K1-diagram-core.md` | composed concept diagrams: parts, on / in / hang / orbit, routing, player | sheet D1–D5, D9, D10 | done (sheet built; live test36: pictures right, values dropped) |
| **M0** | `M0-trust-and-continuity.md` | numbers never changed, recap scope, repeat = same slide, continue the open diagram (another / inside), mishear routing | sheet + live test | **done** (test37–39) |
| M1 | `M1-contact-mechanics.md` | `qty` op (values said later attach), solver framework, contact-mechanics solver (incline, stacked blocks, push, friction regimes, pulley, spring), force arrows + values panel + motion | sheet + live test | **done (test40–41)** |
| M2 | `M2-M5-outline.md` §M2 | look + motion polish, free-body toggle, value-change morph | sheet + live test | done (test42–43) |
| M3 | §M3 | Groq scene extraction (closed vocabulary, validated), paraphrase set | ≥ 90 % paraphrase replay + live test | done (test45–47) |
| M4 | §M4 | 10-min live mechanics lecture, latency budget | live run all must-pass yes | done (test48) |
| M5 | §M5 | motion solver: projectile, free fall, relative velocity (rain–umbrella, cars, river), circular | sheet + live test | **next** |
| later | — | circuits (old K2, MNA), optics, fields, atoms / chemistry (old K3–K4) | one card each | — |
| V3 / Canvas | `docs/v3/V3-story-outline.md` | story, then imagination canvas (people via relation table + attach points, old E3c) | — | after M5+ |

## Parked (kept working as is, no new work)
F-017 stage people scenes (E3c / E4 / E5), F-016 canvas, F-015 scenes. Lines that need people keep today's
behaviour until the Story / Canvas phase.

## Rules that every M card keeps
Numbers said (quote + unit) or computed by Python; missing → symbol, never a default. The LLM states WHAT, never
coordinates or values. Fast path first (0 tokens). Laptop target: 4 GB GPU for STT only; Groq free tier.
