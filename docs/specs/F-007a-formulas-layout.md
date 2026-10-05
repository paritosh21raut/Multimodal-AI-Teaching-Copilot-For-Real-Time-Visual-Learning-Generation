# F-007a: Formulas (KaTeX) + layout polish (V1a)

**Status 2026-10-06: done — implemented, tested, runtime-verified (0-token checks + a real LLM run on the qwen backup).**

Order: **V1a** → V1b images (F-007b) → V1c robustness (F-007c); each finished and verified before the next.
Architecture: `display.md`, `presentation.md`. Contract: `slide-spec.md` (`formula` block).

## What existed (before V1a)
| Part | State |
|---|---|
| `FormulaBlock {latex, spoken, variables[{symbol, meaning, unit}]}` | contract + model |
| Composer `_merge_formula` | set `latex = spoken = ` the model's plain `expression` (no LaTeX) |
| Client `Formula` | showed `spoken` as plain text in a card |
| Prompt | asks `formula: {expression, variables [{symbol, meaning}]}` (no format given) — **unchanged** |

Real `expression` values the model produced (all recorded sessions): `CO2 + H2O → C6H12O6 + O2`,
`6CO2 + 6H2O + light → C6H12O6 + 6O2`, `6CO2 plus 6H2O plus light gives us C6H12O6 plus 6O2`,
`Cardiac Output = Heart Rate × Stroke Volume`, `carbon dioxide plus water, in the presence of sunlight and
chlorophyll, gives glucose plus oxygen`. → Plain text with Unicode operators, sometimes spoken words.

## User answers (2026-10-06)
I write the formula lecture fixture; chemical subscripts everywhere: yes; word equations in the slide font: yes;
slides without an image keep today's centred layout (image layout = V1b); no other polish items for now.

## Design (no prompt change, no extra LLM tokens)
1. **KaTeX 0.16.22 vendored** in `web/vendor/katex/` (`katex.mjs`, css, woff2 fonts only, ~0.9 MB), served with
   versioned URLs + import map like the other client files; no CDN at run time.
2. **`presentation/mathtext.py`** (pure): `to_latex(expression)`.
   - chemistry tokens (element whitelist, needs a count, never a count of 1, single element only for O2/S8-like
     molecules) → `\text{CO}_{\text{2}}`, coefficient `6CO2` → `\text{6}\,…`: the whole formula in the slide font
   - spoken operators: plus, minus, equals / is equal to, gives (us) / produces / yields / forms → arrow, times,
     multiplied by, divided by, squared, cubed; Indian English "m into a" (× between symbols), "half m v squared"
   - "in the presence of X" goes over the arrow (`\xrightarrow{\text{X}}`); "+ light" stays a term, as said
   - symbols vs words decided **per side of = / →** ("Kinetic energy = ½ m v²"); words → `\text{}`; single
     letters stay math italics; `a / b` → `\dfrac`; Greek names / λ Δ; ² ³; "Ohm's law: V = IR" → the formula
   - input that is already LaTeX is kept after a brace-balance check; `\href`, `\def`, … rejected
   - anything else unsafe/unparseable → `latex = ""`, the display shows `spoken`
3. **Composer**: `FormulaBlock(latex=to_latex(expr), spoken=expr)`, `Variable.latex`; truthful substitution edits
   `spoken` and rebuilds `latex`; duplicate check and `describe()` use `spoken`; height from the visible length,
   fractions taller.
4. **Client** `web/shared/rich.js`: `Tex` (KaTeX inline mode so long formulas wrap at operators; render error →
   spoken text), `rich(text)` (chemical subscripts in every slide text: titles, points, facts, groups, steps,
   comparison, timeline, cause/effect, tree, example, callout), `chemParts` (same rules as Python). CSS: `\text`
   in the slide font, operators in the accent colour.

## Layout polish (from real-lecture captures, `artifacts/app/lecture_*`)
| Issue seen | Fix |
|---|---|
| Long step labels render as heavy bold paragraphs (respiration, 2 steps) | `Label: rest` → label + detail; labels > 60 chars regular weight |
| 6-step process: "Oesophagus" spilled out of its card | ≥ 5 steps: compact cards, smaller label, hyphenation |
| "What is human body systems?" | title templates agree with a plural topic ("What are …", "How … work", "What … need") |
| Provisional teaser numbered like a point | unnumbered, dashed marker |
| Cause/effect pairs of different heights when one side wraps | equal-height pairs, text centred |
| **Bug found (M4 composer):** a point containing the slide's term (≥ 12 chars) counted as a duplicate and was silently dropped ("Unit of acceleration: …", "… kinetic energy becomes four times") | `is_duplicate`: containment only when the shorter text is ≥ half of the longer |

## Risks
- The model's expression format varies (symbols vs words) → the converter degrades to `\text{}` / spoken form.
- Two-letter uppercase products ("V = IR") show upright as a name (`IR`); acceptable.
- KaTeX size vs the height model → auto-fit + `SlideOverflow` as for every block.

## Tests (all green 2026-10-06: 269 fast, 7 browser)
- `tests/unit/test_mathtext.py`: every recorded model expression, physics/maths, spoken Indian-English forms,
  pass-through, escaping, chemistry traps (B12, N95, H1N1, A4, COVID19, U2, NaCl).
- `tests/unit/test_formula_slides.py`: block latex/spoken, duplicates, substitution rebuilds LaTeX, fallback,
  fraction height, plural titles, dropped-point regression.
- `tests/e2e/test_formulas_browser.py` (Edge): each formula renders with KaTeX inside the stage, no `.katex-error`;
  fallback text; subscripts in title/points and none for B12/N95; JS `chemParts` == Python `chem_parts`.

## Runtime exit check
Done (0 tokens), screenshots inspected:
- `tools/screenshot_display.py`: 17 slides × 2 themes (3 formula slides, 6 stress slides) → `artifacts/display/`.
- `tools/screenshot_lessons.py {light,dark} physics`: real engine, scripted interpretations of
  `tests/fixtures/lectures/force_motion.txt` → `artifacts/lessons/physics_*`.
- `tools/screenshot_app.py --lecture --simulate tests/fixtures/lectures/force_motion.txt --demo-slides
  --no-understanding --speed 2`: real app, /control + /display render KaTeX, 0 errors → `artifacts/app/lecture_force_motion/`.

Real LLM run (user, 2026-10-06 01:08, session 20261006-010822-cdb5, `--speed 1`): gpt-oss-120b skipped (daily
quota spent), so **8 interpretations by qwen3.8-27b (`groq_alt`, ≈ 33k tokens)**, 2 deterministic fallbacks at the
end (qwen OTPM limit; OpenRouter backup 404 "model unavailable for free"). 5 slides, 0 page errors. Model formulas:
`Speed = Distance / Time`, `v = u + at`, `F = ma`, `KE = 1/2 mv²`. The last one rendered wrongly (1 over "2 mv"):
neither side counted as symbolic → fixed (a lowercase product next to a number is symbolic; "ice → water" stays
words), regression tests added, re-rendered and inspected (`artifacts/app/lecture_force_motion/fixed_ke.png`).
Not yet seen: the same lecture on gpt-oss-120b.
