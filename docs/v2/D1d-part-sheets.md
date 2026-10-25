# D1d — Front view from the WhatsApp part sheets (+ face expression sheets)

_Planned 2026-10-24 after the D1c side-view puppet proof. Characters = 2D puppets cut from art; the engine only
moves them (D1c card). No LLM tokens. `src/` untouched. Output under `artifacts/d1c/` (same page, more views)._

## Inputs (user added, `whatsapp_artifacts/`)
- `Man body parts/` (18): exploded view, face without features, torso, neck cylinder, left/right upper arm,
  sleeve, forearm + hand (2 each), thigh, "skin" (shin?), shoe (`man left show.jpg` = shoe, a typo).
- `man face expressions/` (13): neutral, happy, thinking, surprised, angry (2), confused, crying, shouting, shy,
  sleepy, tired, worried.
- `woman body part/` (12, unnamed WhatsApp files) and `woman face expressions/` (12, incl. excited, laughing).
- Already used: `man in all poses.jpg` (turnaround, the scale/colour reference), D1c side parts.

## Read first (only these)
`docs/v2/D1c-puppet-proof.md`, `tools/imggen/cut_puppet.py`, `artifacts/d1c/index.html` (grep: rig, `fk`,
`drawPerson`, `drawFace`, `CLIPS`), `tools/imggen/shoot_d1c.py`. Look at the images with Read (one contact sheet
of all part images first, made by a small script, not one Read per file).

## Plan
1. **Inventory**: contact sheet of every part image + the exploded view. Write a table: file → part, view
   (front/side/…), side (L/R), problems (scale, colour drift from the turnaround palette, missing parts, the
   two forearm versions — pick the better one). Name the woman files in the table (don't rename on disk).
2. **Generic cutter** `tools/imggen/cut_parts.py`: part image on white → alpha by un-blending from white, largest
   piece, tight crop; pivots per part (joint ends) measured from the exploded view, kept in a small hand-checked
   table in the script; scale every part to the turnaround (head height / limb lengths of `man in all poses.jpg`
   front view); recolour to the sampled turnaround palette if the sheets drift. Output
   `artifacts/d1c/front/parts/*.png` + `front/parts.json` (same schema as the side view).
3. **Front view in the page**: second part set; a person shows `front`, `side` (mirrored for left), and a back
   view only if sheets exist (else say so). View chosen by facing vs camera (8-way later); quick cross-fade on a
   view change. Front clips: idle, wave, point, think, walk toward the camera (simple), push (side stays the
   main push view). Arms/legs rotate in the picture plane; keep D1c's FK/IK/ground clamp.
4. **Front face**: face-without-features part + live code-drawn front face (the D1b round-1 expression logic the
   user liked) matched to the `man face expressions/` sheets; add the new expressions (confused, crying, shouting,
   shy, sleepy, tired, worried). Profile face (D1c) gets the same new set.
5. **Woman** only if the man front view is done and time remains; else it is D1e.
6. Sheets: `shoot_d1c.py` → per theme one contact sheet: reference front vs assembled front puppet, front poses,
   front expressions next to the sheet's expression images, side view row kept. Measure frame ms.

## Rules
- Use the art; never redraw a body part in code (only faces, sleeve shape if the art lacks one, arrows/props).
- Don't change D1c's side view or the round-1 expressions the user liked unless the new sheets require it.
- One review subagent on the diff at the end. Report STATUS / IMPLEMENTED / TESTED / VERIFIED / ISSUES / NEXT.

## Stop point
User judges the front-view man + expressions (contact sheets / live page). Then woman (D1e), boy, D2.

## Result
_(fill ≤ 1 KB)_
