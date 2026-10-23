TASK: Build a 2D puppet rig from reference image for live lecture engine.

REQUIREMENTS:
1. Create SVG with separate <g id=""> layers:
   g-head, g-neck, g-torso, g-l-shoulder, g-l-upperArm, g-l-lowerArm, g-l-hand,
   g-r-shoulder, g-r-upperArm, g-r-lowerArm, g-r-hand,
   g-l-hip, g-l-thigh, g-l-shin, g-l-foot,
   g-r-hip, g-r-thigh, g-r-shin, g-r-foot

2. COLORS (flat fill only, no gradients for 4GB GPU speed):
   skin: #F9D5B0
   shirt: #4FA8B3
   pants: #D8CBB0
   shoes: #8B7E74
   hair: #2E2B29

3. JOINT PIVOTS (normalized 0-1 relative to 1000x1000 canvas, front view):
   neck: [0.50, 0.252]
   l_shoulder: [0.372, 0.322], r_shoulder: [0.628, 0.322]
   l_elbow: [0.242, 0.428], r_elbow: [0.758, 0.428]
   l_wrist: [0.126, 0.508], r_wrist: [0.874, 0.508]
   l_hip: [0.418, 0.528], r_hip: [0.582, 0.528]
   l_knee: [0.378, 0.688], r_knee: [0.622, 0.688]
   l_ankle: [0.354, 0.864], r_ankle: [0.646, 0.864]

   Side view pivots:
   neck: [0.718, 0.252], shoulder: [0.718, 0.332], elbow: [0.718, 0.445],
   wrist: [0.728, 0.562], hip: [0.718, 0.532], knee: [0.718, 0.698], ankle: [0.724, 0.868]

4. ANIMATION LOGIC:
   - Each lower part rotates around its parent joint
   - Use transform-origin = joint coordinate
   - Motion: rotation = lerp(current, target, 0.15) for smooth 60fps
   - For live speech: map keywords to preset poses, e.g. "explain" -> arms open, "think" -> hand to head

5. PERFORMANCE:
   - Render with Canvas 2D or SVG transform only, no WebGL
   - 12 fps pose update, 60 fps render lerp
   - One draw call per limb = <2ms on 4GB GPU

6. EXTENSIBILITY:
   - Keep head:body ratio 1:4.5
   - To create new character (woman/animal/atom), reuse same joint structure, only swap shapes/colors in same <g> ids

OUTPUT: index.html with canvas + rig.json