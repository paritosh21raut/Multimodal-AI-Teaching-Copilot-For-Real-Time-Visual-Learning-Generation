# ADR-0012 — Concept Diagrams: composed live from a part grammar, no templates, no people

Date 2026-10-26 · Status: **proposed** (planned at the user's request; built in K1–K5) · Spec
`docs/v2/F-018-concept-diagrams.md`.

## Context
F-017 draws scenes with people, animals and backdrops. The user asked (E3b start) for pure concept visuals — an
incline, a magnet's field, an atom, a stirred beaker, the solar system, any resistor network — that need no people
or scenery, look like the S0–S4 simulations, follow the science and are built from what the teacher says, without a
template per case. The 21 templates prove the look works but each covers one fixed setup; E4's "diagram recipes"
would repeat that pattern.

## Decision
- A **diagram mode** next to the stage, on the same slide machinery (sim mode, recap, /control, event log,
  validator, provenance).
- The LLM emits ops of a small **part grammar** (parts with ports, series / parallel groups, wires to nodes,
  containment, placement, processes, quoted givens). Python validates, lays out and solves with **general domain
  engines** (netlist layout + MNA, field tracing, shell tables, Kepler, F-017 laws, ray tracing, a curated reaction
  table). The browser plays a `diagram.patch`.
- A **finite part library** (~120 SVG parts, both themes) is the only hand-made art; any composition of parts is
  allowed. Routing to diagram vs stage is deterministic from the line's nouns, with a teacher switch.
- E4's diagram recipes move here; E4 keeps views, the new scene laws and continuity.

## Consequences
- Circuits, fields, atoms, astronomy, lab work and mechanics become open-ended within their domain; unknown parts
  fall back to a labelled box. Chemistry stays within a checked table (no invented reactions).
- The old templates stay for teacher-picked use and as a look reference.
- More sessions before E5 (K1–K5); the evaluation covers both modes.
