# V2 look samples — 2D vs 3D (2026-10-26)

The user wants the basics to be accurate first, says 2D is fine if it is very good, and asked for samples of both.
Same eight teaching sentences drawn both ways (no LLM; the physics comes from closed forms).

| Sheet | What it is |
|---|---|
| `artifacts/v2look/sheet2d_textbook_flat.png` | 2D, incline-template style (cream, ink outline, colour-role arrows), flat people |
| `artifacts/v2look/sheet2d_explainer_flat.png` | 2D, colourful explainer style (sky, ground, soft shadows, no outlines) |
| `artifacts/v2look/sheet2d_textbook_stick.png` | 2D, template style, stick people |
| `artifacts/v2look/sheet_B_toon_more.png` | 3D B toon, 10 scenes, 4 cast looks, clothes normals smoothed, prop palette remap |
| `artifacts/v2look/2d.html?theme=…&fig=…` | 2D scenes **animated** (serve the repo root) |

How the 2D people move: the 87 CC0 motion-capture clips (Quaternius UAL1+2) are baked once into joint tracks
(`motion.json`, 1.5 MB, `tools/imggen/bake_motion.py`); the browser draws the figure from the joints in SVG. So a
2D push / throw / walk / carry / jump / sit is real human motion, not hand-keyed. Walk speed = the clip's own stride
speed (no foot sliding); hands are placed on the box; the throw releases at the clip's release frame.

## What the samples showed
- **2D**: every element sits exactly where the solver says (orthographic by nature); objects that are hard in 3D
  (glass, liquid, pouring, ions, rain, strobe images, vector triangles, split panes) are easy and clear; same look as
  the 21 templates; no WebGL, no asset downloads, light on the laptop next to Whisper. Weak: one viewpoint (side);
  people are simple; "around the object" camera moves are not possible.
- **3D B toon**: people look real from any angle, rich actions. But: muscles show through the clothes (the body
  silhouette itself is muscular; smoothing normals does not fix it), each kit needs palette + scale fixes
  (mint trees, peach rocks until remapped), glass / liquids look weak, overlaps in perspective (man on a rock),
  much more asset work before scenes are reliable. Real clothes need paid outfit packs or modelling.

## Recommendation
2D stage now (textbook style as default, explainer style as the second style pack, stick figures as an option),
people from baked motion capture, objects from a drawn vector kit + recoloured flat icons. Keep the 3D work as a
later option (V3 story shots). F-017 / E-cards get rewritten for 2D after the user's pick.

## Round 2 (user: explainer_flat liked, people could be better; try the toon people in 2D; more + harder scenes)
| Sheet | What it is |
|---|---|
| `sheet2d_people_styles.png` | close-up + line-up of 10 people (man, woman, beard, curly + glasses, bun + skirt, ponytail, boy, girl, elder + cane, elder woman) in 4 styles: flat (round 1), **shaped** (tapered limbs, shaped torso, hips, skirts / shorts, hair styles, bigger eyes), **chibi** (big head), **toon3d** (the 3D B toon body rendered side-on into the 2D scene) |
| `sheet2d_toon3d_scenes.png` | 8 people scenes with the toon3d people inside explainer_flat |
| `sheet2d_animals.png` | procedural 2D animals: dog, cat (sitting), horse, cow, birds, fish; gait synced to speed |
| `sheet2d_explainer_A.png` / `_B.png` | 18 scenes with shaped people: round-1 eight + park (man walks dog), classroom (teacher + 3 seated), tug of war (6 people, arms by IK on the rope), boat across a river (top view, velocity triangle), refraction (Snell, real vs apparent fish), lift (N > mg), water cycle, photosynthesis, circuit (electron flow), orbit |
Animated: `2d.html` (default explainer · shaped; links switch style / people).
Known limits: toon3d people have no IK yet (tug of war shows them pushing), bodies are muscular, barefoot-looking shoes,
no skirts; 2D animals are simple (no 3D animal pack yet); a figure-style choice decides E1.

## Round 3 (user: keep explainer_flat; people = chibi + toon3d, drop flat / shaped; chibi better, toon3d natural + fair)
- chibi: own detail layer (glossy eyes + brows + smile, ear, nose, round hands + thumb, collar, shirt shading, waistband,
  white-soled shoes, hair highlight). toon3d: muscles smoothed away and limbs / chest / hips slimmed on load (Taubin
  smoothing + bone-line scaling), fair skin (texture used only for shading), arm IK (hands on rope / handles / swing),
  each clip grounded like the 2D bake.
- New scenes (`scenes3.js`): seesaw (moments), swing (PE/KE bars), watering (projectile water, growth), germination,
  speed-up (equal-time strobe), echo (mirror-source wavefronts), shadow (similar triangles), rope wave (y = A sin(kx-wt),
  computed lambda / A), floating (U = W), states of matter, magnet (traced two-pole field + compasses), Moon phases.
- Sheets: `sheet2d_people_final.png` (chibi vs toon3d), `sheet2d_new_chibi.png`, `sheet2d_new_toon3d.png`, `sheet2d_topics.png`.
- Limits: toon3d cannot mirror a clip yet (tug of war: hands on the rope, body still leans in); chibi skin tones vary,
  toon3d all fair (as asked); animals stay 2D.
