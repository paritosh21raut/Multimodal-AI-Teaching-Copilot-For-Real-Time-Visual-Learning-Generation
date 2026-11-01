# Prompt for a second opinion — live stick-figure story animation

Copy everything below the line into another chatbot.

---

I need an honest engineering feasibility opinion. Please do not be encouraging for its own sake. If something is
not achievable, say so plainly, and keep "proven today" separate from "research / hope".

## The project
A teaching copilot that listens to a teacher's live lecture (local Whisper speech-to-text, about 0.5–1.5 s per
sentence) and draws on a classroom projector in real time. It already does live slides, physics diagrams computed by
Python solvers, and a "story mode" that detects when the teacher starts telling a story ("Let me tell you the story of
Isaac Newton…") and reads each spoken line into structured beats: time, place, people, who speaks and the spoken words
(including pronouns and continuity across lines). Today, story mode shows a background photo (Wikimedia) with emoji
figures and speech bubbles. The user rejects that.

## What the user wants
A **live animated scene** for every spoken story line, built as the teacher speaks:
- "Newton was sitting under an apple tree" → a cartoon / stick-figure Newton actually *sitting under* a drawn apple
  tree; "an apple fell on his head" → the apple falls and hits him; he looks up, surprised.
- Characters move: walk, run, sit, stand, point, hold things, ride, fall, talk (speech bubbles at the speaker).
- Style like YouTube stick-figure story videos, or cartoon explainers where famous people (Newton, Einstein,
  Marie Curie) appear as recognisable caricatures. Stick figures are acceptable if that is what works live.
- **Not template based**: not a fixed set of pre-made scenes per story. Any story a teacher tells (history,
  science, a journey of a water drop or a blood cell, a simple tale) should compose its own scene.
- It must look live and immersive, not like icons on a photo.

## Hard constraints
- Real time: scene on screen ≤ ~2–3 s after the sentence ends; animation at 30–60 fps in a browser (projector page).
- Hardware: ordinary school laptops, **4 GB GPU or CPU only**; Whisper STT already uses the GPU.
- LLM: free Groq tier only (Llama / gpt-oss class models, ~1–2 s per call, a few thousand tokens per line is OK).
  No paid APIs. No Gemini.
- Architecture rule: the LLM only states WHAT is in the scene (entities, actions, relations) as validated JSON;
  deterministic code computes HOW (layout, poses, motion). The LLM must never write the rendering code.
- No live image generation (too slow / too heavy for 4 GB). Assets prepared offline are allowed.

## What was already tried and failed (please learn from it)
1. A code-built 3D man from primitives: rejected as ugly.
2. A 2D "explainer" stage with chibi cartoon puppets, flat scenery and baked CC0 mocap: nouns were right, but
   **relations were never drawn correctly** (rider beside the horse instead of on it, bird on the ground instead of
   in the sky, objects not held). The parser was mostly regex. It was parked.
3. Current story mode: photo backdrop + emoji standees + speech bubbles: rejected as "not an animated experience".

## Ideas I am considering (critique them, add better ones)
- LLM → a **scene graph** per line: characters (with look attributes), props, actions from an open verb list mapped to
  motions, spatial relations (on, under, in, holding, riding, next to, falling onto), and the camera.
- **Stick-figure / simple 2D rig** with IK, poses computed from the relations (sit *on* a seat point, hold *at* a
  hand point, look *at* a target); walk / run cycles; physics (gravity) for falling objects.
- **Text-to-motion retrieval** from a large mocap set with text labels (HumanML3D / AMASS, KIT-ML, or CC0 sets),
  projected to a 2D stick skeleton, versus small text-to-motion models (T2M-GPT, MoMask, MDM) — is any of them
  fast enough on 4 GB / CPU, and what are the licences?
- **Props by text retrieval** from a big consistent line-art SVG library (game-icons.net, Iconify sets, Noun-style),
  with auto anchors (top surface, base, canopy, inside) from the shape, so relations can attach.
- Famous people: a small offline-made set of caricature heads, or heads composed from attributes (wig, beard,
  glasses, hair colour).
- Renderer: PixiJS / Canvas / SVG + GSAP, or Rive / Spine / Lottie for rigs.

## Please answer
1. Is this feasible **live, open-ended (not templates)** under these constraints? Yes / partly / no, with the reason.
2. Which part is the real hard problem, and how would you solve it? (My guess: turning an open sentence into a
   *correct* picture: relations, attach points, object coverage.)
3. The best concrete stack: libraries, datasets, models and their licences, and the expected latency on 4 GB.
4. What quality to expect honestly, compared with hand-animated YouTube stick-figure videos.
5. Which sentences will look right and which will fail. Please judge these:
   "Newton was sitting under an apple tree." · "An apple fell on his head." · "Napoleon's army crossed the Alps
   in winter." · "Marie Curie worked day and night in a cold shed." · "The drop of water rises into the clouds." ·
   "The boy rode his horse to the village." · "Einstein said to his friend, time is relative."
6. The smallest proof (1–2 days of work) that would show the approach works before investing weeks.
7. Any existing open-source project that already does text → live 2D character animation, and what I can reuse.
