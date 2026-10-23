VISUAL STYLE NAME: edu_flat_v1 — Educative Flat Vector Puppet Style

REFERENCE IMAGES: Use image_20261023_190823.webp (man) and image_20261023_191029.webp (lady) as absolute style reference. Every new object must match them pixel-perfectly.

1. CORE AESTHETIC:
- Flat vector illustration, minimal, clean, educational animation style
- No gradients, no textures, no 3D shading, no drop shadows
- Only solid flat color fills
- Very friendly but NOT cartoonish, NOT childish, NOT anime
- Looks like a high-quality textbook illustration for university/school

2. LINE WORK:
- No thick outlines. If outline exists, it is 0.5px - 1px max, same color as fill but 10% darker, or no outline at all
- For humans: NO visible joint lines except a VERY FAINT natural skin crease at elbows and knees only, 10% opacity of skin shadow color (#E5C5A8 at 0.10 opacity), barely visible to human eye, looks like real skin fold
- For shirts: ONE faint shoulder seam line only, 10% opacity
- For objects (rocket, tree, car etc): NO eyes, NO smile, NO human face ever. Only natural object lines.

3. COLOR RULES:
- Humans: Fixed palette — Skin #F9D5B0, Shirt Teal #4FA8B3, Pants Beige #D8CBB0, Shoes Warm Taupe #8B7E74, Hair #2E2B29
- Animals: Natural colors (dog brown #A68A6A, cat gray #8F8D8A, bird sparrow #8A6A55) but keep same flat fill logic
- Props/Objects: Use THEIR natural real colors (rocket white+red, tree trunk #8B7E74 leaves #5A9A6F, mountain brown #8A7A6F + snow #EAF1F8, lightning cloud dark #2F3E55 + bolt yellow #FFD23F, rain cloud blue-gray #7AA0B8 + drops #6A94B0, football classic black #1A1A1A + white #FFFFFF, atom nucleus blue, etc.) DO NOT force teal/beige on non-human objects.
- Maximum 4 colors per object to keep GPU fast.

4. PROPORTIONS:
- Humans: Head:Body ratio — Adult 1:4.5, Boy/Girl 10yr 1:4, Child 5yr 1:3 (big head)
- Limbs are simple rounded rectangles, hands are mitten shape (no individual fingers), feet are simple oval
- Dog/Cat: Simple geometric body, no detailed fur
- All objects: Simple geometric shapes, minimal details

5. LAYOUT — CHARACTER DESIGN SHEET FORMAT (MANDATORY):
- White background #FFFFFF always
- Top center text: "CHARACTER DESIGN SHEET" in bold dark gray #4A4A4A, then second line "EDUCATIVE ANIMATION, [OBJECT NAME]" in regular
- Two views side by side: Left = FRONT VIEW, Right = SIDE VIEW (90 degree rotation)
- Bottom center labels: "FRONT VIEW" and "SIDE VIEW" in small gray #666666
- Bottom footer tiny text: bullet points with features e.g. "• Natural colors • Flat vector • No face • For educational animation"
- Canvas: 1000x1000 normalized, centered characters, plenty of white space

6. RIGGING FOR ENGINE:
- Each human limb must be separate <g> group: g-head, g-neck, g-torso, g-l-upperArm, g-l-lowerArm, g-l-hand, g-r-upperArm, g-r-lowerArm, g-r-hand, g-l-thigh, g-l-shin, g-l-foot, g-r-thigh, g-r-shin, g-r-foot
- Joint pivots (normalized 0-1 for 1000x1000 canvas):
  Man front: neck [0.50,0.252], l_shoulder [0.372,0.322], r_shoulder [0.628,0.322], l_elbow [0.242,0.428], r_elbow [0.758,0.428], l_wrist [0.126,0.508], r_wrist [0.874,0.508], l_hip [0.418,0.528], r_hip [0.582,0.528], l_knee [0.378,0.688], r_knee [0.622,0.688], l_ankle [0.354,0.864], r_ankle [0.646,0.864]
  Side: neck [0.718,0.252], shoulder [0.718,0.332], elbow [0.718,0.445], wrist [0.728,0.562], hip [0.718,0.532], knee [0.718,0.698], ankle [0.724,0.868]
- For animals: front legs = human arms logic, back legs = human legs logic
- For props (tree, car, rocket, atom etc): No rig, static SVG, but if motion needed use simple transform (e.g. atom electrons rotate around [0.50,0.50], rocket translate y, wheels rotate around center)

7. TECHNICAL PERFORMANCE (FOR 4GB GPU):
- No WebGL, use Canvas 2D or SVG transform only
- One draw call per limb
- Flat fill only, no filters
- Animation: pose update 12fps, render lerp 60fps with lerp(current, target, 0.15)
- Export: transparent PNG + SVG layers + rig.json with normalized coordinates

8. WHAT NOT TO DO:
- DO NOT add eyes, smile, mouth to non-living things (rocket, tree, car, building, mountain, football, rain, lightning, graph, atom)
- DO NOT make tree or car human-like (no arms, no legs)
- DO NOT use thick black outlines like cartoon
- DO NOT use gradients, shadows, or textures
- DO NOT change skin color or shirt/pants colors for humans
- DO NOT add detailed fingers, hair strands, or fabric wrinkles

FINAL CHECK: If you place new object next to image_20261023_190823.webp, it must look like it came from the same designer on the same day, same brush, same flatness.
