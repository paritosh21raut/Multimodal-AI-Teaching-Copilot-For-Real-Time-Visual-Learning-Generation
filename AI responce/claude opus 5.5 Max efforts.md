Design review · Lecture copilot · V2

# Canvas for Imagination

An independent review of the stuck V2: what went wrong, five ways to build it, the one I'd build, and how to prove it works live in a classroom.

**force** **velocity** **acceleration** sureread on the maker's own page or paper estimatemy calculation, a secondary source, or a guess opinionengineering judgement

Contents

1. [Short answer](#answer)
2. [1Diagnosis](#diagnosis)
3. [2Architectures](#architectures)
4. [3Recommendation](#recommendation)
5. [4Tools and assets](#tools)
6. [5Open vocabulary](#open-vocab)
7. [6Scene schema](#schema)
8. [7Build order](#build)
9. [8Research novelty](#novelty)
10. [9System design](#system)
11. [10Traps](#traps)
12. [11Dev tips](#tips)
13. [12Extra features](#features)
14. [13Anything else](#else)
15. [Sources](#sources)

The short answer

## Stop making art. Use art that already moves.

Your bottleneck isn't rendering, prompting or physics. It's asset supply. You need people, animals, vehicles and objects that are rigged, work from any angle and share one style, and you've been trying to make them yourselves. Free CC0 3D libraries already have them. Render those flat so they read as vector art, and spend your engineering on what only you can build: the director, law-synchronised acting and guaranteed-correct numbers. opinion

01Choose the style by supply, not by taste

The only free source of rigged, multi-view, style-consistent people, animals, vehicles and props is CC0 low-poly 3D: Quaternius first, then Kenney, KayKit and Poly Pizza. Build the look on that.

02Go back to approach (f) and swap the geometry

Your engine (clips, IK, arrows, live face, flat renderer) was right. Programmer-made meshes were the problem. Load artist-made rigged meshes, retarget the CC0 Universal Animation Library, keep your live face as a texture.

03Render 3D so it reads as vector art

Toon shading with 2–3 tone bands, one palette per lecture, outlines, an orthographic side camera by default, contact shadows. It's real 3D underneath, so any camera angle still works.

04Drop per-line generation, 2D cut-outs and mixed media

SD-Turbo frames, AI reference sheets, emoji and photos never share one look, and none of them can act.

05Interpret at two speeds

A CPU fast path draws a draft about 1 s after the sentence ends; the LLM delta refines it within about 2 s. The renderer never waits for the network.

06Give every number a provenance

Said, computed or constant. Anything else is a symbol, and the scene gets an “Illustrative” badge. The validator enforces this; prompting can't.

07Add a director

Staging, framing, timing and camera grammar are where “explainer quality” comes from. You have no such layer today.

08Live composes, offline creates

Nothing new is modelled during the lecture. Missing words go down a fallback ladder live, get logged, and are filled by an offline asset factory between lectures.

#### The ceiling, plainly

On a 4 GB laptop you won't get Kurzgesagt-grade bespoke art, any-verb motion, or new consistent characters invented live. The closest achievable version: a consistent flat-shaded 3D stage with exact physics overlays, a draft visual about a second after each sentence, and a library that grows after every lecture.

Assumptions behind the numbers: English lectures, a 1080p projector, classroom Wi-Fi with 100–300 ms round trips, 120–160 spoken words a minute, and a teacher with a phone as a remote.

01 · Diagnosis

## A supply problem, not a rendering problem

You framed V2 as a rendering problem. It's an asset-supply problem plus a missing director. Every approach either had no supply of rigged, consistent art (c, d, g) or tried to manufacture it by hand in code (e, f).

| Approach | Verdict | Why |
| --- | --- | --- |
| (a) 21 templates | Right idea, wrong trigger | Accurate solvers and diagrams, but cue words make the vocabulary closed. Keep the solvers as law modules the scene graph calls. |
| (b) Topic worlds | Right idea, wrong trigger | Same as (a). Fold the worlds into the law and diagram layer. |
| (c) Open canvas | Right pipeline, wrong supply | Speech to ops, Imagine Mode, the focus camera and the safety filter are the right skeleton. Emoji, photos and fixed poses can't share a look or act. |
| (d) SD-Turbo | Wrong for live | Drift and GPU contention come with the method; tuning won't remove them. Your own numbers: 0.41 s alone, 11.6 s beside Whisper. |
| (e) Code-drawn styles | Wrong | Programmer art. Taste doesn't come out of code fast enough. |
| (f) 3D primitive character | Right engine, wrong geometry | Clips, IK, arrows and live faces were good. Primitives shaped by programmers will never look designed. Go back here. |
| (g) 2D cut-outs from AI sheets | Wrong at scale | Views × characters × body parts explodes, AI sheets drift, joint data is wrong, and there's no artist. Drop it. |

### The root problem

- **Coverage versus consistency is a real trade-off for pictures, not for rigs.** Consistency comes from shared topology, rig, material and palette; coverage comes from catalogue size plus a fallback ladder. A 3D library gives both. Images can't, because each image is a new drawing. opinion
- **Acting needs three things you never had together:** a rig, a clip library on that rig, and sockets so a hand can hold, push and release. Photos, emoji and generated images have none of them.
- **Explainer quality comes mostly from staging and timing:** what's on screen, where, when, and what the camera does. You built a camera; you don't have a director. opinion
- **“Looks right” was never defined,** so every round passed the tests and failed the eye.

### Where exactly you're lacking

1. A style chosen by what's available, not by taste.
2. A director: staging, framing, timing, camera grammar, attention.
3. Acting: sockets, IK contacts, and clips time-warped to solver events.
4. Look evaluation: fixed targets, blind pairwise ratings, screenshot regression.
5. Latency design: a draft path that never waits for the LLM.
6. Speech-recognition robustness for the words that become pictures.
7. Provenance as a type: numbers carry where they came from, and the validator refuses the rest.

#### What you already got right

The deterministic core, the LLM as a gated service, Python law solvers, arrows and trajectories, the focus camera, Imagine Mode, the safety filter, live code-drawn faces and a serious test culture (about 1,800 tests plus Playwright). That's most of the hard engineering. The new design puts it at the centre.

02 · Architectures

## Five architectures, judged against your goal

These cover everything on your list: image and video generation, 2D rigs, LLM-written SVG and Manim-style code, rigged 3D libraries and game engines. Each card says how it works end to end; the table below compares them.

Option A

#### Generate pixels per line

speech → LLM prompt → image model with LoRA / IP-Adapter / ControlNet pose / multi-reference → cut-out → stage. Or a real-time video model renders the shot.

- The best open consistency tools are multi-reference editors such as FLUX.2 and Qwen-Image-Edit-2511. They reduce drift but don't remove it, and they give you a picture, not a rig. estimate
- FLUX.2 \[klein\] 4B (Apache-2.0) makes a 4-step image in about 1.2 s on an RTX 5090 using 8.4 GB. It won't fit beside Whisper in 4 GB. sure
- Real-time video needs datacentre GPUs: Krea Realtime 14B reaches about 11 fps on one B200. sure
- Video models don't know physics. On Physics-IQ the best model scored 29.5%, and physical understanding was unrelated to visual realism. sure

**Verdict:** drop as the main path. Keep it only as an asynchronous prop generator at the bottom of the fallback ladder.

Option B

#### 2D rigs: Spine, Rive, Lottie or your cut-outs

an artist builds rigged characters per view → engine plays skeletal clips → solvers drive positions.

- Looks great when an artist builds it. A three-quarter or back view is a new rig.
- Spine Essential is $69 and Professional $369, one-time per seat (sale prices when checked); runtime use needs an editor licence. Rive's web runtimes are MIT; the editor is a subscription. sure
- Animated Drawings (MIT) auto-rigs a single drawing and retargets BVH motion, but it was archived in September 2025 and is side-view only. sure

**Verdict:** drop for open vocabulary. Only worth it with a hired artist and a small fixed cast.

Option C

#### Code draws everything: LLM-written SVG plus Manim-style diagrams

LLM writes SVG or animation code per object or scene → renderer executes it.

- Diagrams as code are the right tool for maths and fields: strips, plots, vectors, waves, field lines. That's where the 3Blue1Brown look comes from.
- LLM-drawn objects: icons are fine, complex characters fail (the OmniSVG paper reports StarVector failing on complex characters). sure
- Token maths kills it on your quota: one decent SVG object is roughly 1,500–4,000 output tokens, so 8k tokens a minute allows 2–5 objects before anything else happens. estimate
- Agentic Manim systems (TheoremExplainAgent: 93.8% success with o3-mini; Code2Video) are batch pipelines, not live ones, and still show layout issues. sure

**Verdict:** keep the diagram half as a layer, written by you, not by the LLM. Drop LLM-drawn objects live.

Option D · recommended

#### Vector-look 3D stage on a CC0 rigged library

speech → fast-path draft + LLM scene delta → validator → event-sourced scene graph → law solvers → director → three.js stage rendered flat with outlines, plus a diagram layer and a fallback ladder.

- Characters: Quaternius Universal Base Characters (CC0; 6 bodies, 20 hairstyles, humanoid rig) animated by the Universal Animation Library 1 and 2 (CC0; 120+ and 130+ clips). sure
- The same artist covers animals, vehicles, buildings, furniture, food and nature, so the world matches the people. sure
- Shaded flat with outlines it reads as vector art, but it stays true 3D: any camera angle, no drift.
- Runs on what you have: a few low-poly characters at 1080p is light work for an RTX 3050. estimate

**Verdict:** build this. It's approach (f) with artist-made geometry, plus a director.

Option E

#### Option D inside a game engine (Godot, Unity, Unreal)

same pipeline, but an engine process renders and streams frames onto the slide.

- Better animation tooling (blend trees, state machines) and editors.
- A second runtime beside the browser, harder to draw on the slide, Unreal is heavy for a 3050 laptop, and you'd rewrite working three.js code.

**Verdict:** skip. No visual gain for this look. Revisit only for VR or AR.

| Option | Look | First visual after speech | GPU / cost | Open vocabulary | Character consistency | V3 stories | Main risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A · Generate pixels | Great single frames; sequences don't match | 1–6 s cloud estimate; 11.6 s local beside Whisper (your measurement) | Doesn't fit 4 GB with STT; about $0.0005–0.05+ per cloud image | Highest | Low to medium | Poor: identity drifts across shots | Wrong physics; no acting |
| B · 2D rigs | High, with an artist | Instant | Tiny GPU; artist time plus licences | Very low | High | Good for a fixed cast | No artist; views × characters explode |
| C · Code draws all | Excellent for maths; weak for things | \< 0.1 s diagrams; 2–10 s per LLM-drawn object | No GPU; quota-bound | Concepts yes, things no | Perfect for diagrams, poor for objects | Poor | “Not imagination” |
| D · 3D library stage | Clean flat-shaded explainer; consistent | ≈ 0.4–1.0 s draft; ≈ 0.8–2.2 s full estimate | Light GPU; ≈ 3–7 US cents per lecture-hour of LLM when paid | High: catalogue plus ladder | High | Excellent | Can look “game-like”; verbs limited to the clip library |
| E · Game engine | Same as D | Same as D | Heavier | Same as D | Same as D | Good | Second runtime; rewrite |

03 · Recommendation

## Build the vector-look 3D stage

In your terms: go back to approach (f), keep its engine, and replace the geometry with artist-made CC0 meshes and clips. Keep the pipeline of (c). Fold the solvers of (a) and (b) into law modules. Drop (d), (e) and (g).

### Why this one

- It removes the coverage-versus-consistency trade-off instead of fighting it: one artist's catalogue, one rig, one shader, one palette.
- It's the only option where “a man pushes a box” is a real action: a rigged body, a push clip, hand IK on the box, and a solver-driven slide.
- It keeps every camera promise: any angle, zoom to the electron, “seen from the man”.
- It needs no GPU beyond rendering, so Whisper keeps the GPU.
- It's the strongest base for V3: a cast of real 3D characters can't drift between scenes.
- It puts your best work (solvers, arrows, live faces, deterministic core, tests) at the centre of the product.
- Precedent: simple flat-shaded 3D with real simulations already reads as a quality explainer; look at the Primer channel's videos. opinion

### How it should look

- **Shading:** unlit or toon with 2–3 bands; colours come from a 10–12-swatch lecture palette, remapped per material when the asset loads.
- **Lines:** outlines about 2 px at 1080p, a darker shade of the fill rather than black.
- **Camera:** orthographic side view by default, like a textbook figure; perspective only for “fly around” moments.
- **Ground:** one ground line or soft floor, blob contact shadows, no background clutter.
- **Faces:** your live canvas face drawn onto the head as a texture (blink, gaze, expressions, mouth shapes). Check each model's face UVs first. estimate
- **Motion:** clips plus IK, eased; optionally hold poses for two frames (“on twos”) for a hand-made feel.
- **On the slide:** the stage is a transparent WebGL layer over the slide. The director treats the slide's title and bullet boxes as no-go zones. In Imagine Mode the slide text dims and the stage takes the whole slide; on End, the last frame drops into the deck as a figure.
- **Overlays:** your vector arrows and labels on top. Colour encodes the quantity type (force, velocity, acceleration) so it means the same in every scene.

### Keep, change, drop, add

| Decision | Items |
| --- | --- |
| Keep | Speech to LLM scene ops; deterministic core; Python law solvers; arrows, trajectories and focus camera; Imagine Mode; safety filter; live code-drawn faces; pytest and Playwright; three.js. |
| Change | (f) character → artist meshes plus Universal Animation Library clips. (a)/(b) templates → law modules and diagram recipes that `law` ops call. Photo search → off the critical path (V1 slides only). Speech recognition → confidence-aware, with a “fix word” button for the teacher. The rule “said or computed” → “said, computed or constant”, with constants such as g taken from a cited table. |
| Drop | Per-line image generation on the laptop (d); code-drawn art styles (e); 2D cut-outs from AI sheets (g); emoji and photos on the stage; cue-word triggers. |
| Add | Director; fast path; validator with provenance; event log; asset lookup with fallback ladder; offline asset factory; look targets and a rating harness; teacher remote. |

### Features to change or add

- **Change** “correct relative real-world sizes” to a scale policy: true scale inside an interacting group (man and box), compressed scale across groups with a “not to scale” badge (Sun and Earth).
- **Change** “any angle” to “any angle, side view by default”; voice or the teacher's phone switches it.
- **Change** “same face, same body” to a cast built from base bodies, hair, outfits and palette, stored in a registry. Characters are assembled, not invented.
- **Add** the Illustrative badge, a predict–observe–explain pause, and teacher-only nudges (section 12).

#### Not possible live on this hardware, and the closest version

- **Inventing a new, consistent, animatable character or object per sentence.** Closest: compose from library parts, generate props asynchronously, create new characters offline.
- **Any verb as real motion (“juggle”, “pirouette”).** Closest: the 250-odd clips of both animation libraries (fewer in their free versions), nearest-verb mapping and procedural IK actions (reach, point, hold, push, look). Real-time text-to-motion such as NVIDIA's ARDY wants a big GPU: its default text encoder alone takes about 14 GB of GPU memory (a slower CPU option exists). sure
- **Kurzgesagt- or 3Blue1Brown-grade bespoke art per scene.** Closest: one consistent style pack and strong staging.
- **Numbers for quantities nobody stated.** Closest: symbols plus the Illustrative badge.
- **Fluids, smoke or cloth with exact numbers.** Closest: stylised particles with no numbers.
- **True relative size for everything at once.** Closest: the scale policy with its badge.
- **Photoreal people or photo backdrops in the scene.** They don't fit the style; keep photos on V1 slides.

### Your examples, built this way

| Teacher says | Built from | Solver and what's computed | Live? |
| --- | --- | --- | --- |
| “A man pushes a box across a rough floor” | Base character, box, floor; push clip with hand IK on the box | Sliding friction. N and mg computed; deceleration after he stops is computed once μk is said, otherwise symbolic with the badge | Yes |
| “Rain falls vertically, but a man walking forward feels it slanted” | Walking man, rain particles; frame switch with the camera parented to the man | Relative motion. θ = atan(vman/vrain) computed when both speeds are said; otherwise tan θ = vm/vr as a symbol | Yes |
| “An electron orbits the nucleus… now focus on the electron” | Bohr-atom diagram recipe from template (a); `focus` camera shot | Qualitative orbit. A “Bohr model is a simplification” nudge goes to the teacher's phone, not the projector | Yes |
| “Throw a book in the air” | Man and book; throw clip time-warped so the release frame lands on the solver's t0; book on the hand socket until release | Projectile. Dotted path from computed points; apex and range only if speed or angle is said | Yes |
| “If you jumped on the Moon and then on Mars” | The same cast member twice in a split view; jump clip scaled to the solved height | Projectile with constants gMoon = 1.62 and gMars = 3.71 m/s². For the same take-off speed the heights are ≈ 6.1× and ≈ 2.6× Earth's (computed) | Yes |
| “Split the area under the curve into thin strips” | Diagram layer: axes, curve, strips n → 2n → 4n | Riemann sums computed only if the function is said; otherwise a generic curve with no numbers | Yes |
| “A lightning rod protects a building” | Building, rod and cloud from the kit, lightning bolt, field lines | Qualitative electrostatics recipe; no numbers | Yes |
| “The solar system” | Planet kit and orbit diagram | Kepler periods from the constants table; scale-policy badge | Yes |
| “Two cars collide” | Car models from the library | 1D collision: momentum, with restitution from the wording (“stick together” means e = 0); numbers only if masses and speeds are said | Yes |
| “A wave on a string” · “Electric and magnetic fields of a wave” | Diagram layer: string as a polyline; perpendicular E and B sine waves in 3D | Wave solver; wavelength, frequency and speed only if said | Yes |
| “A bicycle under the ocean” | Bicycle from the library; underwater environment preset (gradient, caustics, bubbles) | None | Yes |
| “A laptop flying on top of an airplane” | Laptop and airplane props; `on` relation uses the plane's top socket; flight path; the camera follows | None | Yes |

04 · Tools and assets

## What to use now, and what to buy later

The free path runs on your RTX 3050 laptop and free tiers. The paid path is what to switch on when money or a bigger GPU arrives. Licence notes flag the catches that bite research projects.

| Layer | Free path, now | Paid or bigger GPU, later | Licence and catches |
| --- | --- | --- | --- |
| Speech to text | faster-whisper medium.en (keep). Groq whisper-large-v3-turbo is a free cloud option that frees the GPU: 20 requests a minute, 2,000 a day, 7,200 audio-seconds an hour. sure | NVIDIA Nemotron ASR Streaming 0.6B (cache-aware, chunks of 80–1,120 ms); or a cloud stream such as Deepgram Nova-3 via Cloudflare at $0.0052 a minute | faster-whisper MIT. Check each model card; I couldn't find Nemotron's memory needs for a laptop GPU |
| End of turn | Silero VAD plus Smart Turn v3.2 (8 MB int8 model, about 10–100 ms on CPU) sure | Same | Smart Turn BSD-2-Clause; Silero VAD MIT |
| Fast-path language | spaCy `en_core_web_sm`; WordNet through `wn` or NLTK; `pint` for units | Same | MIT, MIT/Apache-2.0, BSD. The WordNet licence is permissive |
| Scene LLM | Groq `openai/gpt-oss-20b` with a cached prompt prefix; `gpt-oss-120b` as fallback. Free: 30 requests a minute, 1,000 a day, 8,000 tokens a minute, 200,000 a day per model sure | Same models, paid: $0.075 in / $0.30 out per million tokens for 20b, about 1,000 tokens a second sure | gpt-oss weights Apache-2.0. Groq's page doesn't make clear which plan its table shows; it matches the 8k you see |
| Safety | Local list plus the LLM's `safe` field; `gpt-oss-safeguard-20b` only for flagged lines (3 requests a minute free) | Same, at higher limits | Policy is yours to write |
| Renderer | three.js (you're on r160): `MeshToonMaterial`, `OrthographicCamera`, `OutlineEffect` | Same | MIT |
| Animation | three.js `AnimationMixer` and `SkeletonUtils.retargetClip`; headless Blender for offline retargeting and baking | Same | MIT; Blender is GPL, and its output is yours |
| Characters | Quaternius Universal Base Characters (6 bodies, 20 hairstyles) and Modular Character Outfits; KayKit Adventurers; Kenney characters | Commission 4–6 hero characters on the same skeleton so every clip still works | CC0. KayKit and Kenney details come from secondary sources estimate |
| Motion clips | Quaternius Universal Animation Library 1 and 2 (120+ and 130+ clips; the free Standard version has a subset, 45 clips for Library 1); Mixamo for gaps | Quaternius Source tier (Patreon); NVIDIA ARDY on a 16–24 GB GPU or in the cloud (4-step model, 33 ms average generation latency, tested on an RTX 4090) sure | Libraries CC0. Mixamo: free with an Adobe ID, no redistribution of raw files, reportedly in maintenance mode estimate. ARDY code Apache-2.0, weights under NVIDIA's Open Model licence |
| Props, animals, vehicles, places | The Quaternius catalogue; Kenney; KayKit; the Poly Pizza API (10,000+ low-poly models) estimate | Same, plus offline image-to-3D with TRELLIS.2 | Poly Pizza is mostly CC-BY, so you need a credits screen |
| Icon fallback | Microsoft Fluent Emoji, flat SVG style (about 3,100 icons) | Same | MIT. OpenMoji (CC BY-SA 4.0) works if you accept share-alike on derived art |
| Async image fallback | Cloudflare Workers AI `flux-1-schnell`: a 512² image at 4 steps costs 43.2 neurons, so the 10,000 free neurons a day buy about 230 images sure | Recraft V4 vector styles: about $0.05 an image, SVG output, a custom style from 1–10 references estimate. Or FLUX.2 \[klein\] 4B on your own GPU | FLUX.1 \[schnell\] and klein 4B Apache-2.0; klein 9B non-commercial |
| Cut-out and vectorise | u2netp (you have it) plus vtracer | Same | Apache-2.0; MIT |
| Image to 3D (offline only) | None | TRELLIS.2 (4B, GLB output) on a rented GPU | TRELLIS.2 reported MIT estimate. Hunyuan3D 2.1's licence excludes the EU, UK and South Korea |
| Diagram layer | Your own three.js/SVG primitives; Motion Canvas and Manim CE as design references | Same | MIT |
| Tweening | anime.js or tween.js | GSAP, now free with all plugins, after a licence read | MIT. GSAP's standard licence bars use in tools that compete with Webflow's visual animation builder |
| Rigid bodies beyond closed form | Rapier or MuJoCo on the server, producing trajectories | Same | Apache-2.0, both |
| Testing and rating | pytest, Playwright, pixelmatch; a small pairwise-rating page | Same | MIT / Apache-2.0 / ISC |
| Cloud GPU | None | Modal: $30 a month of free credits on Starter; research grants up to $10k sure | Check current terms |

### Spend the first money on

1. **LLM tokens.** Paid Groq removes the 429s for about 3–7 US cents per lecture-hour. Cheapest fix in the whole project. estimate
2. **A 3D generalist for a week.** Retargeting, sockets, palette baking, and 4–6 hero characters on the shared skeleton. Probably a few hundred US dollars per character on freelance markets. estimate
3. **A 16–24 GB GPU or rented hours** for the offline factory: FLUX.2 \[klein\], TRELLIS.2, ARDY.
4. **Recraft vector styles** for props that match your style exactly.

05 · Open vocabulary

## Words outside the library, without breaking the style

Resolve each noun separately, then compose. Odd combinations like “a bicycle under the ocean” are a composition problem, not an asset problem. Every rung renders with the same shader, palette and outline, so the style holds even when the asset is a stand-in.

| Rung | What happens | Live cost | Example |
| --- | --- | --- | --- |
| 0 · Sense | The LLM supplies a WordNet synset and the validator checks it exists. The fast path guesses the commonest sense and is corrected later. | \< 10 ms | “bat” in a biology lecture → `bat.n.01`, the animal |
| 1 · Exact | Synset → tagged library asset | \< 10 ms | “dog” → dog model |
| 2 · Neighbour | Nearest hypernym or sibling within two steps, with a label chip showing the spoken word | \< 10 ms | “sedan” → car, chip “sedan” |
| 3 · Kit | Parametric shapes for physics and concept nouns: rod, prism, lens, coil, magnet, cloud, planet, cell, wave. Code-drawn is fine here; explainers draw concepts as simple shapes. | \< 20 ms | “lightning rod” → thin rod with a tip |
| 4 · Cut-out | Flat SVG icon → palette recolour → extruded “cookie-cutter” prop with an outline | ≈ 50–100 ms the first time, then cached | “trumpet” → extruded icon |
| 5 · Generate | Asynchronous: style-prompted image (Cloudflare flux or Recraft) → cut-out → vectorise → palette quantise → extrude. Hot-swaps rung 4 and is cached forever under the synset. | 2–6 s, off the critical path estimate | “astrolabe” |
| 6 · Placeholder | Labelled rounded box. Honest beats wrong. | Instant | Whatever is left |

### Rules for the ladder

- **Never block on rungs 4–5.** Show the best rung available now and upgrade later with a short morph.
- **Cache by synset, not by word.** Log every miss with its sentence; the offline factory fills the top misses each week.
- **Speech errors:** a visual noun with low word confidence appears ghosted, and the teacher's phone shows “did you mean…?” with the alternatives. Pass V1 slide titles and recent nouns to Whisper as its initial prompt to bias it toward the lecture's vocabulary. That's how “spear” stops becoming “keyboard”.
- **Sense from context:** the entity table and lecture topic go to the LLM, and the validator rejects synsets whose category clashes with the role (the object of `throw` must be a thing that can be thrown).
- **Safety first:** lookup runs after the safety gate. Generated assets pass an image safety check and, optionally, a tap to approve on the teacher's phone.

06 · Scene schema

## How the LLM should describe a scene

- The LLM says **what and who**. Never how much (unless quoting), never where in pixels, never when in milliseconds.
- It outputs a **delta** (operations) against the current scene, not a whole scene.
- Positional arrays, short keys, ids from the entity table. A delta is usually 80–250 tokens.
- Numbers arrive **only inside `given`**, with a verbatim quote from the sentence.
- The LLM **binds the roles of a law**; the solver computes everything else.

| Op | Arguments | Meaning |
| --- | --- | --- |
| `add` | id, kind (agent, prop, surface, place, field, diagram), {w, syn, attr} | Introduce an entity: the spoken word, its synset, attributes |
| `rel` | id, relation (on, under, in, behind, holding, attached_to, left_of…), id | Spatial or physical relation |
| `act` | id, verb, {agent, obj, dir, manner} | An action; the director maps it to a clip plus IK |
| `end` | id | Stop an action (“now he stops pushing”) |
| `law` | id, law name, role bindings | Attach a solver: sliding_friction, projectile, relative_motion, collision_1d, orbit, wave_string, field_static… |
| `given` | law id, symbol, {v, u, q} | A stated number, its unit and its verbatim quote |
| `view` | mode, ids | Frame of reference (“seen from the man”) or a split comparison (“Moon versus Mars”) |
| `cam` | shot, ids | establish, medium, close, focus, follow |
| `diagram` | id, recipe, params | Plots, strips, vectors, field lines |
| `fix` · `del` | id, field, value · id | Correction (“not a box, a crate”) · removal |
| `personify` | id | Put a live face on any object (for V3) |

```
// "A man pushes a box across a rough floor."
{"vis":"scene","ops":[
  ["add","p1","agent",{"w":"man","syn":"man.n.01"}],
  ["add","b1","prop",{"w":"box","syn":"box.n.01"}],
  ["add","s1","surface",{"w":"floor","syn":"floor.n.01","attr":["rough"]}],
  ["rel","b1","on","s1"],
  ["act","a1","push",{"agent":"p1","obj":"b1","dir":"right"}],
  ["law","L1","sliding_friction",{"body":"b1","surface":"s1","force_from":"a1"}],
  ["cam","establish",["p1","b1"]]
],"safe":"ok"}
// "The box has a mass of 10 kilograms and he pushes with 50 newtons."
{"vis":"scene","ops":[
  ["given","L1","m",{"v":10,"u":"kg","q":"a mass of 10 kilograms"}],
  ["given","L1","F",{"v":50,"u":"N","q":"pushes with 50 newtons"}]
],"safe":"ok"}
// "Now he stops pushing."
{"vis":"scene","ops":[["end","a1"]],"safe":"ok"}
```

What the validator lets through after the first two sentences. Mass and push were said; N and mg are computed from them and the constant g; μk was never said, so friction and acceleration stay symbols, the motion is drawn as an illustration, and the scene carries a badge. Colour encodes the quantity type, so a force is red in every scene and labels tell forces apart. If you want one colour per force, vary lightness inside the red family so “red means force” still holds.

### Fitting inside 8,000 tokens a minute

| Part of each call | Tokens | Counts toward the limit? |
| --- | --- | --- |
| Static prefix: rules, op grammar, law catalogue, 6 short examples | ≈ 1,000–1,200 | No, when served from Groq's prompt cache sure |
| Entity table: up to 25 rows of id, synset and two attributes | ≈ 150–250 | Yes |
| Last two sentences, the current one, and the fast-path draft | ≈ 120–200 | Yes |
| Output: brief reasoning (effort “low”) plus ops | ≈ 150–300 | Yes |
| Counted per call | ≈ 450–750 |  |

- **Per minute:** the fast path only calls the LLM for visual sentences, about 3–5 a minute, so ≈ 1,400–3,800 counted tokens a minute. That fits under 8,000. Without the cache it's ≈ 4,500–9,000, and you hit the wall. estimate
- **Per day:** 200,000 tokens ÷ 450–750 ≈ 265–440 calls, about 55–145 lecture-minutes per model per day. Using both gpt-oss models doubles it. The 1,000-requests-a-day cap doesn't bind first. estimate
- **Paid:** 180–360 calls an hour at list prices comes to ≈ 3–7 US cents per lecture-hour, before the 50% discount on cached tokens. estimate
- **Caching rules:** the prefix must be identical and first, prompts must pass a model-specific minimum length (roughly 128–1,024 tokens), and the cache expires after about two hours unused. Groq says cached tokens don't count toward rate limits, but bursts of parallel calls can still hit them, so keep calls sequential. sure
- **On a 429:** switch to the other model, then to fast-path-only mode. The stage never stalls.
- Use Groq's JSON or structured-output mode where the model supports it, and always validate with pydantic.

### What the validator checks

- Schema and ids: referenced ids exist, new ids are unique.
- Synsets exist in WordNet, and their category fits the role.
- Numbers: each `given.v` matches a number in its quote; the quote appears in the sentence after normalising number words; the unit fits the role's dimension (`pint`).
- Law preconditions: required roles are bound to compatible kinds, e.g. sliding friction needs a body on a surface and a force source.
- Budgets: at most 16 ops per delta and 12 visible entities; past that the director groups or swaps things out.
- Safety: `safe` must be “ok” and the local filter must agree, or the delta is dropped and logged.
- Everything rejected is logged with its reason. That log is a dataset for your paper.

07 · Build order

## A convincing result fast, then breadth

1. **Look gate (3–4 days).** One Quaternius character, a box and a floor in three.js with toon shading, palette, outlines and an orthographic side camera. Run a blind vote with at least 10 people against frames from your approaches (f) and (g). Continue only if it wins clearly. If not, spend two more days tuning the look spec, not the geometry.
2. **The pushed box, live (2 weeks).** Fast path, LLM delta, validator with provenance, sliding-friction solver, push clip with hand IK, free-body arrows, the Illustrative badge, Imagine Mode on the slide.
3. **Director and continuity (2 weeks).** Staging rules, camera grammar, sockets; “he stops”, “he pushes harder”, “add a second box”; the throw with release sync; the Moon/Mars split; the rain frame switch.
4. **Library and ladder (2 weeks).** Ingest Quaternius, Kenney and KayKit; tag them with synsets offline (LLM proposes, CLIP checks, a human approves); icon cut-outs; the async generator; the odd prompts.
5. **Diagram layer (2 weeks).** Plots, Riemann strips, vectors, field lines, string waves. Port the 21 templates as law modules and recipes.
6. **Evaluation and pilot (2 weeks).** A corpus of about 300 sentences from real lectures, golden replays, screenshot diffs, pairwise rating, and a small classroom pilot with comprehension questions.

**Postpone:** V3 story ops, multilingual, ARDY and image-to-3D (paid path), AR, student devices.

### The success test

| Metric | Target | How it's measured |
| --- | --- | --- |
| First visual: end of sentence to first pixel | p50 ≤ 1.0 s, p95 ≤ 2.0 s | Timestamps in the event log |
| Full scene | p95 ≤ 3.0 s | Same |
| Unsupported numbers on screen | 0 | Automatic: every rendered number must map to a provenance record |
| Displayed versus recomputed numbers | 100% match | Independent re-solve in tests |
| Scene correctness | ≥ 85% of visual sentences show the intended entities, relations and actions | Two annotators on the corpus |
| Physics correctness | ≥ 95% judged physically right | A physics teacher reviews 50 scenes |
| Look (“explainer quality”) | Raters pick the live frame ≥ 40% of the time against hand-staged frames made with the same assets (50% means they can't tell); preferred over approach (c) in ≥ 80% of pairs | Blind pairwise test, at least 20 raters, Bradley–Terry scores |
| Stability | Fewer than 1 visible retraction a minute | Event log |
| Learning | A measurable gain over slides alone | Pilot study with predict–observe–explain questions |

#### How you'll know it's “explainer quality”

When teachers and students can't reliably tell a live frame from a hand-staged frame made with the same assets, the live system is as good as the style allows. Past that point quality is an art question about the style pack, not an engineering one. opinion

08 · Research novelty

## What makes it publishable

No published system I found combines live lecture speech, multi-sentence continuity, guaranteed-correct numbers and characters whose actions are synchronised to physics. Each of these can carry a claim with a number attached. opinion

1. **Provenance-typed scene deltas from live speech.** Every quantity on screen is said, computed, constant or symbolic, enforced by a validator. Claim: zero unsupported numbers by construction, against measurable hallucination when an LLM writes the scene or the code directly. Metrics: unsupported-number rate, value error.
2. **Two-speed speculative interpretation.** A CPU draft within about a second, an LLM refinement after, reconciled by morphing rather than popping. Metrics: time to first visual against retraction rate, compared with LLM-only.
3. **Law-synchronised acting.** Clip events (contact, release, footstrike) are time-warped and IK-constrained to solver events. Metrics: event-alignment error in ms, contact violations, foot sliding, perceived plausibility.
4. **Continuity with bounded context.** An event-sourced scene graph and a fixed-size entity table resolve “he”, “it” and “the second car” across sentences. Metrics: co-reference accuracy and continuity errors a minute, against full-transcript prompting at a fraction of the tokens.
5. **Style-preserving open-vocabulary lookup.** The synset ladder plus style-locked generation and caching. Metrics: coverage on held-out nouns, style distance, human style-consistency ratings.
6. **A benchmark.** Annotated lecture sentences with gold scene deltas, givens and comprehension questions. Datasets get cited.

| Work | Input | Timing | Numbers | Characters |
| --- | --- | --- | --- | --- |
| WordsEye (2001) | Typed text | Offline | n/a | Static poses |
| Holodeck, SceneCraft (2024) | Text | Offline | n/a | None |
| TheoremExplainAgent, Code2Video (2025) | Prompt | Batch | Inside LLM-written code, unchecked | None |
| MoVer (2025) | Prompt | Offline | Verifies motion properties against the prompt | 2D motion graphics |
| GPT4Motion, PhysGen (2024) | Text or image | Offline | Simulator-driven motion, generated pixels | None |
| RealityTalk (2022), DrawTalking (2024) | Speech, plus sketch | Live | None | Simple |
| This design | Live lecture speech | ≈ 1–2 s | Provenance-guaranteed | Rigged, synced to solvers |

- Also adjacent: LLM2Manim generates narration and Manim code in parallel for responsiveness, but from prompts rather than live speech; ALIVE answers lecture questions through an avatar in about 1–2 s. MoVer's verify-then-repair loop (58.8% correct first try, 93.6% after up to 50 repair rounds) is the closest cousin to your validator. sure
- **Venues:** IEEE ICALT, IEEE FIE or IEEE AIVR for the V2 system paper; IEEE Transactions on Learning Technologies once you have the classroom study. opinion
- **One paper per version:** V2 is provenance plus synchronised acting; V3 is cross-shot continuity, camera grammar from narration and extractive captions; V4 is a language-neutral scene graph with cross-lingual evaluation.

09 · System design

## From speech to pixels

Speech becomes words on the laptop; the fast path drafts operations and prefetches assets while the cloud LLM writes a scene delta. Only the validator can write into the scene graph. Solvers and the director turn the graph into a timeline the projector renders. Missing assets come from the ladder, with cloud generation as a later hot-swap.

| Component | Runs on | Budget | Notes |
| --- | --- | --- | --- |
| Mic, VAD, end of turn | Laptop CPU | 10–100 ms | Silero plus Smart Turn; emits sentence boundaries sooner than a fixed silence timeout |
| Speech to text | Laptop GPU | 200–600 ms per sentence estimate | faster-whisper medium.en; word confidences; rolling partials for prefetch |
| Fast path | CPU | \< 50 ms | spaCy parse, lexicon, numbers and units, pronouns → draft ops and a prefetch list. Never binds numbers to laws |
| Scene-delta LLM | Groq | 0.5–1.2 s estimate | Cached prefix, JSON output, fallback model, fast-path-only mode if it fails |
| Validator | CPU | \< 5 ms | Schema, provenance, units, law preconditions, budgets, safety |
| Scene graph | CPU | \< 1 ms | Append-only event log; state is a fold over the log; undo is a compensating event |
| Law solvers | CPU, Python | 1–20 ms | Closed form first, a rigid-body engine only when needed. Output: samples, event times, quantities with provenance |
| Director | CPU | \< 10 ms | Staging, camera grammar, timing, attention, scale policy, slide no-go zones, clip sync |
| Asset lookup | CPU and disk | \< 10 ms on a hit | Synset index, ladder, prefetch cache; logs misses |
| Generator | Cloudflare or Recraft | 2–6 s, async | Hot-swap; cached by synset |
| Projector | Browser on the laptop GPU | 16 ms a frame | three.js stage over the slide, diagram layer, overlays |
| Teacher phone | Phone browser |  | Pin, undo, fix word, camera, End Imagine Mode, approvals, nudges |

### The director, in brief

- **Staging:** a ground line at about 70% of the height; motion reads left to right; the agent stands on the side the action comes from; the slide's text boxes are no-go zones.
- **Framing:** the camera fits the entities of the current sentence, with margins and thirds.
- **Timing:** entrances staggered by about 100 ms; actions start after entrances settle; arrows appear once motion starts; numbers appear when computed and stay pinned to their arrows.
- **Camera grammar:** establish, then act, then focus. Never move the camera during a key physics moment unless asked.
- **Attention:** desaturate entities nobody has mentioned for a while; highlight the one just named.
- **Acting sync:** clips carry event frames (contact, release, footstrike). The director time-warps them to solver events, keeps hands on objects with IK during force intervals, and sets walk playback speed to the solver's velocity so feet don't slide.

### Rules the system follows

1. The LLM proposes, the validator disposes. Nothing reaches the scene any other way.
2. Every number has a provenance; otherwise it's a symbol.
3. The renderer never waits for the network. Draft first, refine later, morph instead of popping.
4. The event log is the single source of truth: replayable, undoable, testable, exportable.
5. Style is locked per lecture: one style pack of assets, palette, outline and fonts.
6. Bounded context: the entity table and the last two sentences, never the whole transcript.
7. Degrade, don't fail. LLM down: fast path only. Asset missing: the ladder. Solver can't bind: qualitative plus the badge. This also covers you without a local LLM.
8. The teacher can override anything in one tap.
9. Determinism: the same transcript and seed give the same frames. That's what makes tests and papers possible.
10. Show less, correctly. The director removes what the current sentence doesn't need.

### How V2, V3 and V4 share it

- **Shared core:** event log, scene graph, solvers, director, asset lookup, renderer, style pack.
- **V3 adds a story layer:** `beat` (a time-ordered slice of the log), `shot` (establish, medium, close, pan, cut, cross-fade), captions taken only from spoken words, a cast registry (body, hair, outfit, palette and face settings, persisted so a character returns identical), a set registry for places, and `personify`: your live face on any object, so the water drop and the red blood cell can be characters.
- **V4:** synsets are language-neutral through the Open Multilingual Wordnet, so lookup, solvers and rendering don't change. Speech recognition, the fast-path parser and captions are per language.

10 · Traps

## What not to do

- **Tuning your way out of a supply problem.** Two rounds of making (f) prettier made it worse. That was the signal.
- **Letting the LLM write runtime code** (Manim, three.js, SVG). Slow and non-deterministic; the agent systems that do it are batch pipelines.
- **Per-line image or video generation.** No rig, no continuity, no physics.
- **Multi-view 2D without an artist.** Views × characters × parts grows faster than any team.
- **Mixed media on one stage.** Emoji plus photos plus 3D reads as stickers however well it moves.
- **Decorating.** Extra, interesting-but-irrelevant detail reduces learning (Mayer's coherence principle). Show what the sentence says, nothing more.
- **Flicker.** Drawing mid-sentence and then retracting. Prefetch on partials, commit at end of turn, morph corrections.
- **Trusting speech recognition on the words that become pictures.** Use confidence, alternatives and the teacher's fix button.
- **Showing numbers because the solver needed them.** The solver may need some μk to animate; the screen doesn't have to show it.
- **Rotating several free accounts to dodge rate limits.** Likely against the provider's terms, and fragile. Pay the few cents.
- **Licence debt.** CC-BY models need visible credits; OpenMoji is share-alike; Mixamo forbids redistributing raw files, so they can't go in a public research repository; FLUX.2 \[klein\] 9B is non-commercial; ARDY weights have NVIDIA's own licence; GSAP restricts some uses; Hunyuan3D 2.1 excludes the EU, UK and South Korea.
- **Real-size purity.** The Sun and Earth at true scale show nothing. Use the scale policy.
- **Trusting green tests about looks.** Unit tests can't judge a frame. You need screenshots and people.

### Mistakes I see in yours

- Choosing the art style before checking where thousands of assets would come from.
- Making reference sheets with a chatbot: no rig data, drift between sheets, manual measuring forever.
- Photo search on the critical path (about 5 s cold).
- Cue-word triggers in (a) and (b): a closed vocabulary by design.
- Sharing one 4 GB GPU between speech recognition and generation without a budget.

11 · Development tips

## Build, test and judge looks efficiently

- **Write a one-page style spec before code:** palette hex values, outline width, shading bands, camera, fonts, maximum moving objects, entrance timings. Judge against it, not against taste.
- **Pick 3–5 look targets** (reference frames) and compare screenshots side by side with them.
- **Golden scenes:** 50 scripted sentence sequences replayed deterministically, screenshotted by Playwright and diffed with pixelmatch. People review only the frames that changed.
- **A weekly blind pairwise vote** on a 50-line web page with 10–20 raters. Fit Bradley–Terry scores, ship the winner, and never debate looks in a meeting.
- **Timebox look work:** two variants, one vote, decide. Endless “looks wrong” rounds come from having no target and no vote.
- **Make the asset factory scripts, not handwork:** headless Blender normalises scale from your real-size table, sets pivots, adds sockets (`hand_l`, `hand_r`, `head_top`, `seat`, `top`), bakes the palette, exports compressed glTF, renders thumbnails, computes CLIP embeddings and proposes synset tags.
- **Annotate clip events once per clip** (contact, release, footstrike). The director needs them for sync.
- **Test with real lectures** (with consent) and real speech-recognition output, errors included.
- **Reuse:** assets, clips, outline shaders, tweening, retargeting, voice and turn detection. **Build:** director, validator, provenance, solvers, sync and evaluation. Those are your paper.
- **Profile on the real laptop with Whisper running,** and give the GPU an explicit budget.
- **Upgrade three.js deliberately.** Toon and outline code depends on its examples modules, which change between releases.

12 · Extra features

## What would make it clearly better for teachers and students

- **Teacher remote on the phone:** pin, undo, fix word, freeze, show numbers, camera presets, End.
- **Predict–observe–explain pause:** “What happens when he stops pushing?” The scene freezes, students predict, then it plays. Strong pedagogy, almost free to build on an event log.
- **What-if by voice:** “twice the mass” re-solves the scene and shows the previous run as a ghost for comparison.
- **Teacher-only nudges:** misconception chips on the phone (“Bohr orbits are a simplification”). Never contradict the teacher on the projector.
- **Scenes become slide figures** in the V1 deck. After the lecture, export a replay video and a PPTX with embedded clips.
- **Student view by QR code:** the same scene with sliders for the stated quantities.
- **Accessibility:** never colour alone (labels and line styles too), a high-contrast palette, captions, a reduced-motion mode.
- **Analytics from the event log:** scenes that get undone or pinned show where the gate or the lookup is wrong.

13 · Anything else

## What you'll need beyond the code

- **Consent and data.** Classroom audio includes students. Keep speech recognition local by default, send only text to the cloud, store transcripts only with consent, and go through your institution's ethics process; the IEEE evaluation needs it anyway.
- **A licences page in the app,** generated from asset metadata (author, licence, URL). Publish only CC0 and CC-BY assets with the research artefact.
- **Team.** A few days of a 3D generalist saves weeks of programmer art.
- **Hardware for the paid path.** A 16–24 GB NVIDIA GPU covers FLUX.2 \[klein\], TRELLIS.2 and ARDY experiments; or rent by the hour. The live path doesn't need it.
- **Reproducibility.** Deterministic replays, the corpus and a CC0 style pack let reviewers re-run your results.
- **Risk register.** If the look gate fails, try a second style pack (KayKit or Kenney) before anything else. If key verbs lack clips, use Mixamo plus IK actions, then ARDY offline. If free tiers change, keep the paid switch one config line away.

Sources

## What this is based on

Read during this review in October 2026. Prices and free tiers change, so check before you depend on one. “Secondary” marks write-ups by third parties.

### Free tiers and pricing

- [Groq — rate limits](https://console.groq.com/docs/rate-limits), [models and prices](https://console.groq.com/docs/models), [prompt caching](https://console.groq.com/docs/prompt-caching)
- [Cloudflare Workers AI — pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Modal — pricing](https://modal.com/pricing)
- [BenchLM — Cerebras free tier](https://benchlm.ai/md/free-tier/cerebras.md) (secondary)

### Characters, motion and assets

- [Quaternius — catalogue](https://quaternius.com/), [Universal Base Characters](https://quaternius.itch.io/universal-base-characters), [Universal Animation Library](https://quaternius.itch.io/universal-animation-library)
- [OpenGameArt — Universal Animation Library](https://opengameart.org/node/174563), [Library 2](https://opengameart.org/content/universal-animation-library-2); [Digital Production on Library 2](https://digitalproduction.com/2026/02/10/130-animations-one-rig-zero-drama/) (secondary)
- [Cinevva — free rigged characters](https://app.cinevva.com/guides/free-rigged-3d-character-models) and [free game assets](https://app.cinevva.com/guides/game-assets-guide.html) (secondary)
- [Poly Pizza](https://poly.pizza/)
- [Adobe — Mixamo FAQ](https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/m-p/13234775) (2022 wording)
- [NVIDIA — ARDY](https://research.nvidia.com/labs/sil/projects/ardy/), [code](https://github.com/nv-tlabs/ardy), [paper](https://huggingface.co/papers/2607.08741)
- [Meta — Animated Drawings](https://github.com/facebookresearch/AnimatedDrawings)
- [Microsoft — Fluent Emoji](https://github.com/microsoft/fluentui-emoji), [OpenMoji](https://openmoji.org/), [Open Peeps](https://pablostanley.gumroad.com/l/openpeeps)
- [PhET — licensing](https://phet.colorado.edu/en/licensing/html)

### Tools and generators

- [Rive — web runtime](https://github.com/rive-app/rive-wasm), [Spine — purchase](https://esotericsoftware.com/spine-purchase), [GSAP — standard licence](https://gsap.com/community/standard-license/)
- [Black Forest Labs — FLUX.2 \[klein\]](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence), [ComfyUI — klein 4B measurements](https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing)
- [BuilderAI — instruction image editing compared](https://builderai.tools/blog/ai-image-editing-flux-kontext-qwen-image-edit-step1x) (secondary)
- [OpenRouter — Recraft V4 vector styles](https://openrouter.ai/recraft/recraft-v4-styles-vector)
- [Krea Realtime 14B](https://huggingface.co/krea/krea-realtime-video); [awesome-realtime-video-generation](https://github.com/yepicaiaaron/awesome-realtime-video-generation) (secondary)
- [CMARIX — open image-to-3D models](https://www.cmarix.com/blog/top-open-source-ai-models-for-3d-image-generation/) (secondary)
- [NVIDIA — Nemotron ASR Streaming](https://build.nvidia.com/nvidia/nemotron-asr-streaming/modelcard), [Pipecat — Smart Turn](https://github.com/pipecat-ai/smart-turn)

### Research

- [Physics-IQ](https://arxiv.org/abs/2501.09038) ([WACV 2026](https://openaccess.thecvf.com/content/WACV2026/html/Motamed_Do_Generative_Video_Models_Understand_Physical_Principles_WACV_2026_paper.html))
- [MoVer](https://arxiv.org/abs/2502.13372), [TheoremExplainAgent](https://arxiv.org/abs/2502.19400), [Code2Video](https://neurips.cc/virtual/2025/131666), [LLM2Manim](https://arxiv.org/abs/2604.05266), [ALIVE](https://arxiv.org/abs/2512.20858)
- [SceneCraft](https://arxiv.org/abs/2403.01248), [OmniSVG](https://arxiv.org/abs/2504.06263)
- [DrawTalking](https://research.adobe.com/publication/drawtalking-building-interactive-worlds-by-sketching-and-speaking/), [RealityTalk](https://ilab.ucalgary.ca/publications/uist-2022-liao/)
- Cited from memory, without links: WordsEye (SIGGRAPH 2001), Text2Scene (CVPR 2019), Holodeck (CVPR 2024), LayoutGPT (NeurIPS 2023), GPT4Motion (2024), PhysGen (ECCV 2024), Visual Captions (CHI 2023), Perlin's Chalktalk, Mayer's multimedia-learning principles, and the Primer YouTube channel.