# ADR-0015 — Live story animation: a language-driven procedural scene engine · 2026-11-01

**Status:** accepted (user: "evaluate … make a final decision"). Replaces the ST1–ST4 story **display** (photo
backdrop, emoji standees, Ken Burns). Keeps the story **language layer** (detector, beats, cast, pronouns, bubbles,
held-line LLM pattern). Sources: `AI responce/` (ChatGPT, DeepSeek, Perplexity, Antigravity) on
`docs/v3/STORY-ANIMATION-OPINION-PROMPT.md`.

## Context
The user wants each spoken story line to become a live animated scene ("Newton was sitting under an apple tree" →
he sits under a drawn tree), stick figures / cartoon OK, not templates. Two earlier stages failed (3D man; F-017 chibi
stage, test35: nouns right, **relations never drawn**). All four reviewers agree:
- Feasible: 2D stick rigs at 60 fps, IK, gravity / contact, LLM → validated JSON, composing unseen stories from
  reusable mechanics. Not feasible: any noun / verb automatically right, hand-animated quality, guaranteed ≤ 3 s on
  the free tier.
- The hard problem is **grounding** (language → relations that are geometrically true), not rendering.
- No text-to-motion models in the live path (5–30 s on CPU, VRAM taken by Whisper; AMASS / HumanML3D non-commercial).
- Raw icon retrieval does not work: an icon has no seat, grip, canopy or saddle. Interactive props need authored anchors.

## Decision
1. **Not text-to-animation; a scene-composition engine.** The LLM states WHAT (entities, events, relations) as a
   **delta against a persistent world** (ids, revision); Python compiles relations into constraints; the browser
   executes motion. Same rule as ADR-0001 / ADR-0014.
2. **World state** (Python, `src/copilot/story/world.py`): entities (person / animal / prop / place / group / agent),
   identity (cast id, known person), posture, attachments (held_by, rides, on, in), region, environment (sky time,
   weather, ground). The previous line's relations stay until changed. Stale answers (old revision) are dropped.
3. **Closed executable vocabulary** (the original verb kept as metadata):
   ops `enter, exit, move_to, follow_path, change_posture(stand|sit|lie|kneel|crouch), attach(hold|ride|sit_on|in),
   detach, fall, throw, look_at, point_at, speak, react(surprise|happy|sad|angry|scared|think), work(act_on prop)`;
   relations `on, under, in, next_to, above, behind, in_front, between, towards, away_from`.
   An unmapped verb → an explicit fallback (the actor stays + caption), logged; never a guessed gesture. Embellishment
   (surprise after a hit) only as a named style rule, never as a story fact.
4. **Compiler** (Python, deterministic): relation → anchor / region / path / contact time. `under tree` = ground
   inside the canopy span clear of the trunk; `ride` = pelvis on saddle, rider parented to the horse; `fall onto head`
   = drop from an anchor to the head contact point; `in shed` = cutaway interior. Output: a `StorySceneSpec` (resolved
   placements, attachments, timed events) for the browser. Python gives the targets and contact times; the browser
   only animates them.
5. **Renderer** (browser, `web/story/anim/`): Canvas 2D (no build step; PixiJS only if Canvas is too slow), one
   line-art style, procedural 14-joint stick rig with 2-bone analytic IK, gait / sit / lie / point / hold / talk /
   react, simple gravity + contact, tweens, speech bubbles at the head anchor (ST1–ST3 logic), sky / weather layers.
   Animation never waits for the LLM.
6. **Assets** (offline, curated, one style): ~40 interactive props drawn in code or as SVG with **anchor sidecars**
   (`web/story/anim/assets/*.json`: anchors, regions, scale in metres, capabilities: rideable / sittable /
   container / holdable), plus static props (game-icons CC BY / Lucide ISC / Tabler MIT, line style, credited) with
   bbox anchors only. Quadruped rig (horse, dog) and a blob agent (water drop, blood cell). A small anchor-marking
   dev page. Real-world scale keeps an apple smaller than a hand.
7. **Famous people**: the stick body + curated head overlays (Newton wig, Einstein hair + moustache, Curie bun,
   Napoleon bicorne, Gandhi glasses …, ~12 offline). Unknown people: attributes from a closed set (hair, beard,
   glasses, hat, clothing colour), gender only from said words (ST2).
8. **Groups and environment**: "army", "crowd" → a group entity of 6–12 instanced figures moving together; "winter",
   "day and night", "cold" → environment ops (snow, sky tween, shiver), not people.
9. **LLM**: one Groq call per story line (bounded context: world summary + last 2 lines + vocabulary), strict JSON
   schema; gpt-oss-20b vs llama-3.1-8b chosen by measured accuracy + latency in P0. The fast path (beats) still puts
   speech bubbles and the cast up at 0 tokens while the call runs.

## Gate (go / no-go, P0 proof, before any big build)
- 20 unseen sentences (not in the prompt): correct supported relations ≥ 16 / 20; valid JSON 100 %.
- Animated tests: **A** "Newton was sitting under an apple tree." (sits under the canopy, apples on branches)
  **B** "An apple fell on his head." (that same apple detaches, falls, touches the head, he reacts)
  **C** "The boy rode his horse to the village." (no gap between rider and horse while moving)
  **D** "Einstein said to his friend, time is relative." (faces the friend, bubble at Einstein).
- Line end → first frame p50 ≤ 2.5 s, p90 ≤ 4 s; ≥ 30 fps on the laptop.
- **The user watches A–D and says yes / no to the look.** No → stop the feature.
No progress is claimed from replay tests or slide counts (test35 lesson).

## Consequences
- Coverage is finite by design: the engine composes freely within its ops, props and rigs; new kinds of props are
  asset work. Napoleon / Curie need groups + environment (P2), not in P0.
- Quality target: a clean live stick explainer ("a moving diagram of the story"), not a hand-animated cartoon.
- Not reused: the photo backdrop / emoji / Ken Burns view; F-017's chibi puppets and mocap stay parked.
- Study only (no copying): hmelberg/stick (no licence), Synctoon (GPL-3.0).

## Cards
P0 proof (2 sessions: LLM relation accuracy, rig + compiler + A–D, user look check) → P1 world + compiler + live
wiring (ops, continuity, fallbacks) → P2 assets, quadruped, blob agent, groups, environment, heads → P3 10-min live
story lecture (the ST4 script) → P4 evaluation (paper 3).

## Addendum 2026-11-02 — after P0 (user "yes, but" + ChatGPT review, `AI responce/chatGPT.txt`)
P0 passed: relations 17/20 (gate 16), look accepted after one round (name tags for named people only, main
characters distinct, supporting ones alike, children / old by said words, group walk). Adopted from the review:
**semantic actions compiled into choreography graphs** (give = approach → reach → handoff → release, over the
primitives; the LLM states meaning, never the sequence); a verb earns its own action only if it needs a unique
constraint, multi-entity coordination or a state change; an **op registry** (preconditions, effects, duration,
failure: a failed transfer keeps the owner); an **affordance registry** in the sidecars with a four-way check
(executable / unsupported / invalid / missing asset); groups, weather and time_jump as world state; environment
grammar (forest, village) and a room builder; a **story-split benchmark** scored per atomic event with failure
types and per-genre numbers. Changed: actions are added ~12 at a time, ordered by the benchmark's UNKNOWN_ACTION
counts (not a guessed 25); benchmark 24 stories first (free tier); pursuit paths precomputed in Python (no runtime
controller); cook / build / fight later; latency gate stays p50 ≤ 2.5 s / p90 ≤ 4 s. Cards: P1a benchmark +
registries → P1b actions batch 1 → P1c live wiring → P2 world (environments, rooms, groups, weather, props) → P3 → P4.
