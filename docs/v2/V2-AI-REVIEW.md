# V2 — review of the 7 AI answers (2026-10-26)

Prompt: `V2-V3-solution-request-prompt.txt`. Answers: `AI responce/` (Claude Opus 5.5, ChatGPT, Gemini, DeepSeek,
Qwen, Perplexity, Antigravity). This note says what they agree on, what each added, what we take, what we drop, and
what we **checked ourselves** before deciding.

## 1. Verdict (all 7 agree)
Our problem is **asset supply**, not rendering, prompting or physics. We kept trying to *make* art (code-drawn
styles, 3D primitives, AI sheets → 2D puppets) or *generate* it per line (SD-Turbo); neither gives consistent,
rigged, any-angle characters. Answer: **use art that already moves** — free CC0 rigged 3D libraries, rendered flat
(toon + outline) so they read as explainer art, with our deterministic core, solvers, arrows and camera on top.
| Our approach | Verdict (consensus) |
|---|---|
| a/b templates, topic worlds | right solvers, wrong trigger → keep solvers as law modules / diagram recipes |
| c open canvas (emoji + photos) | right pipeline (speech → ops, Imagine Mode, camera, safety), wrong supply (stickers) |
| d SD-Turbo per line | wrong for live (drift, no rig, GPU fight with Whisper) → drop |
| e code-drawn styles | programmer art → drop |
| f code-built 3D man | right engine (clips, IK, arrows, face, 144 fps), wrong geometry → keep engine, swap meshes |
| g 2D puppets from AI sheets | views × characters × parts explodes → drop |

## 2. Who added what (and whether we take it)
| Idea | From | Take? |
|---|---|---|
| Quaternius Universal Base Characters + Universal Animation Library 1+2 (CC0, one skeleton) | Claude, Perplexity, Qwen, Antigravity | **Yes** — verified below |
| Toon 2–3 bands + coloured outline, orthographic side camera default, one palette per lecture | Claude, Gemini, Antigravity | **Yes** (look spec) |
| Kenney / Quaternius / KayKit / Poly Pizza props, all through one shader | all | **Yes** (CC0 first; CC-BY needs a credits page) |
| Fallback ladder: exact → near asset → parametric kit shape → flat icon extruded → labelled placeholder; never a wrong picture | Claude, DeepSeek, Perplexity, Antigravity, ChatGPT | **Yes** |
| Provenance on every number (said / computed / constant / symbol) + "Illustrative" badge | Claude, ChatGPT | **Yes** (formalises our rule) |
| Two-speed: 0-token draft from the sentence, LLM delta refines; renderer never waits | Claude, ChatGPT | **Yes** |
| A **director** (staging, framing, timing, camera grammar, attention) | Claude | **Yes** — the main missing layer |
| Acting sync: clip events (contact, release, footstrike) time-warped to solver events; hand sockets + IK; walk speed = solver speed | Claude, ChatGPT, Antigravity | **Yes** |
| Event-sourced scene graph (replay, undo, tests, paper) | Claude, ChatGPT | **Yes** |
| LLM outputs semantic deltas (what/who/relation/law roles), never coordinates, numbers only with a quote | Claude, DeepSeek, Gemini | **Yes** |
| Groq prompt caching + gpt-oss-20b + compact deltas (≈450–750 counted tokens / call) | Claude | **Yes** (measure first) |
| Whisper initial prompt from slide titles / recent nouns; low-confidence nouns ghosted + "fix word" | Claude, ChatGPT | **Yes** |
| Diagram layer (plots, strips, vectors, fields, waves) written by us, not the LLM | all | **Yes** |
| Blind pairwise rating + golden screenshot replays instead of "looks wrong" rounds | Claude, ChatGPT, DeepSeek | **Yes** |
| Predict–observe–explain pause, what-if ghost, scene → slide figure | Claude, ChatGPT | Later (E5 / V2.1) |
| Rapier / Cannon physics in the browser | Antigravity, Qwen | **No** — Python solvers stay the truth |
| LLM writes Manim / SVG / three.js code | — (all reject) | **No** |
| Text-to-3D (TripoSR, Meshy), video gen, ARDY text-to-motion | various | **No live**; paid offline path later |
| Smaller Whisper (tiny/base) to free VRAM | Gemini | **No** (accuracy first; GPU has room) |
| Rive / Spine 2D rigs | all mention | **No** (needs an artist) |
| Godot / Unity | Qwen, DeepSeek | **No** (three.js works) |
| Ollama local LLM fallback | Qwen | **No** (user rule) |
| "Drop open vocabulary, ~70 % coverage" | Qwen | **No** — keep open language; only the *picture* may be a stand-in |

Best single answer: **Claude** (most concrete: director, provenance, acting sync, ladder, token maths, success
metrics). ChatGPT added the clearest quantitative / qualitative / illustrative modes; DeepSeek the "semantic vs
visual open vocabulary" framing; Antigravity the NPR shader detail; Perplexity a clean phase plan.

## 3. What we checked ourselves (2026-10-26) — things the answers got wrong or missed
- **Downloads work** from this machine: OpenGameArt (direct zips), itch.io (scripted free download), kenney.nl
  (direct zips). Google Drive packs hit "too many downloads" → avoid Drive-only packs.
- **Animation Library 1+2 (Standard, CC0) = 89 clips**, incl. Push_Loop, OverhandThrow, Walk/Jog/Sprint, Jump,
  PickUp_Table, Walk_Carry_Loop, Sitting, Swim, Driving_Loop, Idle_Talking, Idle_FoldArms, Yes/No, Interact.
  UAL2 + both base characters + hair share **one 65-bone skeleton**; UAL1's Unreal FBX has the same bones (only
  `root` differs) → clips play with no retargeting.
- **Missed by all:** the free Base Characters are bodies **in underwear**; the matching outfit pack is paid ($20) and
  fantasy-themed. Fix found: **paint clothes per vertex by bone region** (shirt / sleeves / pants / shoes) in our
  shader → any outfit colour, modest, zero art. Proven in the sample sheet.
- Library hair is sized for the base heads, not the mannequin (sits inside it).
- Kenney mini characters: clothed and cute but blocky, 7-bone rig, no push/throw.
- Free base bodies have **no face bones / blendshapes** → full live expressions are not free (see plan §faces).

## 4. Samples made (look gate input)
`artifacts/v2look/index.html`, sheet `artifacts/v2look/sheet_light.png` (tools/imggen/shoot_v2look.py): push with
F / f / v, throw with dotted path, street (car, tree, two people), face close-up — for **A** mannequin + painted
clothes + drawn face, **B** base body + painted clothes + library hair (toon and flat), **C** Kenney mini.
Recommendation: **B toon**. A's drawn hair reads as bald; C reads as a toy.
