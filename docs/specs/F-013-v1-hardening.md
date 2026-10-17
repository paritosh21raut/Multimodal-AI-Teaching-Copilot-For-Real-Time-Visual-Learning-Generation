# F-013 — V1 hardening: evaluation of tests 1–30 and the fix plan

Status: **S1 implemented**, **S2 implemented, targets partly met** (2026-10-16; see "S1 result" / "S2 result"),
**S3a implemented** (2026-10-17, 0 tokens), **S3b implemented** (2026-10-17, 34,808 tokens A/B; see "S3 result"),
**S3c implemented** (2026-10-17, 31,338 tokens A/B) + performance mode, start card picker, Follow removed (from S4).
S4 (rest), S5 planned. Evaluation spent 0 tokens.
Inputs: `verify_results/test1..30` (slides.md, transcript, terminal log, slide PNGs), `_eval/e2e_d2.json`,
`_eval/results.json`, annotator A workbooks (12 lectures), the user's 12 reported issues (2026-10-16).
User answers (2026-10-16): best system first (free Groq now, a paid LLM later); faded provisional content is OK;
websites now open (no web work); PDF images = the user's own STM32 PDFs; fix the truthfulness bug too; find problems
beyond the reported ones.

## 1. Evaluation — measured over tests 1–30 (349 min, 459 slides)

| Area | Measure | Value |
|---|---|---|
| Latency | speech → slide (D2) | **11.2 s median, 27.2 s p90**; waiting for the unit to close 7.6 / 18.2 s; LLM 1.9 / 4.1 s; STT 0.7 / 1.0 s |
| Boundaries | new-topic detection (12 annotated) | P 0.80, **R 0.54** (half the topic changes missed) |
| Boundaries | slides that are a "(part N)" continuation | **322 / 459 (70 %)**; runs of 7–9 parts in tests 8, 27, 30 |
| Hierarchy | relations from the model | elaboration 567, same 419, sibling 165, new_topic 86, **sub_concept 15** |
| Hierarchy | earlier subtopic title reused for different content | 12 (test5, 8, 26, 30, …) |
| Comparison | comparison phrases spoken → comparison slides | **~100 → 5**; 2 of the 5 render with empty headings |
| Definitions | definition card whose term = slide title | **152 / 385 (39 %)** |
| Garbage | coverage-guard "shown as said" units | 117 (source of most raw/garbled points) |
| Mishearing | statements annotated wrong | 57 recorded (26 of them as said: STT) |
| Truthfulness | applied concerns that changed 0 elements | **152 / 287** |
| Images | searches accepted | 214 / 222; lectures with 0 images: 1, 16, 29; same image repeated in a deck: 25 |
| Robustness | full lecture on fallback (Groq unreachable) | test29: 12 slides all titled "Lecture (part N)" |
| Robustness | crash | "No space left on device" in `usage.save` + event log at shutdown (test15) |
| STT | backlog warnings | test12, up to 7 utterances pending |

## 2. Problems (ID → evidence → cause)

### A. Responsiveness
| ID | Problem | Evidence | Cause |
|---|---|---|---|
| A1 | Slide trails speech by 11–27 s | e2e_d2 | gate waits for a whole unit (pause / 40 words / 12 s + 6 s hold) + 8 s wall-clock floor |
| A2 | Nothing shows when a topic is announced; list items appear only after the unit | user #1 | all display goes through the LLM interpretation |
| A3 | Tail of the previous topic lands on the new slide (and vice versa) | test18 CNN drawbacks on the RNN slide; test19 VBT limits on "Inner and Outer Orbital"; test4 Rutherford limits | a unit straddles a topic cue; boundary cut only after a finished sentence + 6 words |
| A4 | LLM down → no topic names | test29 "Lecture (part 1–12)" | fallback has no topic detector |
| A5 | STT falls behind | test12 backlog 7 | medium.en slower than real time under load (not reproduced) |

### B. Structure: topic / subtopic / hierarchy (user #3, #5)
| ID | Problem | Evidence |
|---|---|---|
| B1 | Subtopic changes missed → long "part N" runs | test27 "Ethical Hacking vs Penetration Testing" ×8 (incl. password tips, careers); "Hacker Types" ×8; test30 "Semiconductors" ×9, "Half Wave Rectifier" ×7 |
| B2 | Flat hierarchy: announced children are not linked | test3 Elements / Compounds not under Pure Substances; test11 sexual / asexual as "Reproduction (part N)"; test5 no Alkaline Earth Metals subtopic |
| B3 | Implicit subtopics (no cue phrase) missed | test30 doping, n-type, photodiode ("is called an n-type semiconductor") |
| B4 | Return / revisit reuses an old title for new content | test30 photodiode → "Reverse Bias"; test5 Mg / bleaching powder → "S-Block Elements"; test26 2nd "VLSI Design Flow" |
| B5 | Topic header stale | test28 Deserts / Rivers under "Water Cycle"; test12 "Animals" |
| B6 | Content attached to the wrong concept | test13 Midbrain on the Forebrain slide, Thalamus under Cerebrum; test2 Pascal's law under Fluid Dynamics |

### C. Representation and content quality (user #2, #4)
| ID | Problem | Evidence | Cause |
|---|---|---|---|
| C1 | Comparisons missed; >2 items impossible | FPGA vs ASIC, EH vs PT, AI vs DL, isotopes / isobars / isotones as lists; test18 3-way table with empty headings and "TNN:" prefixes; test5 " vs " | schema `compare: [a, b]`, `pairs{left,right}`; no comparison cue |
| C2 | Definition card repeats the title; non-definitions in the card | 39 %; "Hypothalamus: Hypothalamus:"; "Electron: was discovered…" | composer always shows the term |
| C3 | Same fact twice (formatted + as spoken) | test4 "~10⁻⁸ cm" + "10 to the power minus 8"; test7, test5, test30 s44/45, test13 | coverage guard does not normalise spoken numbers / units / symbols |
| C4 | Garbled or meta text on slides | "[note] Just it can be understood…", "Will come out of the cell…", "Type 2", "Single inverted comma b1 semicolon end end module", "There you went, let us start…", "[unclear location, likely mis-heard]", fragment notes | coverage guard + model notes have no quality gate |
| C5 | Misheard terms kept although the lecture shows the right one | "Wannesbord theory" right after "Valence Bond Theory" on screen; ANM / ENM / "neuromotor"; Sky City (scarcity); territory sector; Prokaryotic Effect; Morse salt; "Labels" (labile); Prussia (→ wrong fact); Descartes (Calonne); Metal clay (matter) | no lecture glossary; correction left to the model |
| C6 | Formula notation | hν0, λ0, `\text{λ\T}`; test16 Schrödinger lecture shows no equation | no subscript normalisation for spoken "nu naught" etc. |
| C7 | Text walls, monotone layouts | key_points 189 of 459 adds; test30 nearly all key_points; group lists (Allied / Central powers) as text; "members" for non-members | representation choice weak for long lectures |
| C8 | Spoken code as bullets | test26 Verilog | no code block |
| C9 | Facts mixed into a timeline | test6 "Distance: 240 miles" in the timeline | composer |
| C10 | Complex equations cannot be spoken (Schrödinger, Maxwell, Navier–Stokes): nothing shows | test16 (whole lecture on the equation, no equation); user 2026-10-16 | formulas come only from what was said |

### D. Images (user #12 + gaps)
| ID | Problem | Evidence |
|---|---|---|
| D1 | No image where one helps | tests 1, 16, 29: 0; need decided only by the model's hint |
| D2 | Same image on several slides | 25 repeats (test12 circulation diagram ×2, test13 brain lobes ×2) |
| D3 | Captions of figures from PDFs are page junk | "65,523 Modes of Reproduction…", "flflf difft ltThttf…", "7,46,745 The Human Brain dlbiihb10…" |
| D4 | Own PDFs: weak figures | raster only (ESP-WROOM datasheet: 0 figures, vector drawings ignored); STM32 labels = caption + body text (60 words); CLIP gate made for photos, not IDE screenshots; byjus brain figures lost by margins < 0.05 |

### E. Truthfulness
| ID | Problem | Evidence |
|---|---|---|
| E1 | Applied concern changes nothing (STATE known issue) | 152 / 287; heart lecture |
| E2 | Model infers facts not said | test4 "Cannot explain alpha scattering" on Rutherford; test6 "march began on 6 April"; test10 a cut-off line finished; test15 kinetic energy blue / green reversed (S3c check: "quantum numbers all zero" WAS said) |

### F. /control UI (user #6–#11)
| ID | Problem | Cause |
|---|---|---|
| F1 | Tab labels / badges overlap when My Notes is wide | `.tabs` labels hidden only by a fixed rule, not by width |
| F2 | Notes page grows / shrinks while speaking | Follow turns pages; `<img>` has no reserved box |
| F3 | Drop area flickers | `onDragLeave` fires on every child (`web/control/app.js:786`) |
| F4 | Follow is inaccurate | user: remove it |
| F5 | Start card grows with many materials; no web link there | chip list; web links only in My Notes |
| F6 | Web chips all named "byjus.com" | file name = host, not the page title |

### G. Robustness
| ID | Problem |
|---|---|
| G1 | Disk full → traceback at shutdown, usage file not saved |
| G2 | `lecture_move ignored` warning at every start (17×) |

## 3. Fix plan (sessions)

Every session: 0-token checks first (`tools/v1_eval.py`, prompt rebuilds, unit tests), then a small live A/B on
gpt-oss-120b (≤ ~45k tokens, reported), screenshots, docs + STATE. A prompt change ships only if the A/B is not worse
on truthfulness (memory: llm-usage-direction).

### S1 — Baseline metrics + responsiveness (A1–A4, G2)
1. `tools/v1_eval.py` (0 tokens): the table in §1 per test + totals, from slides.md / logs / sessions; saved as the
   baseline (`verify_results/_eval/v1_baseline.json`). Re-run after every session.
2. **Cue detector** (deterministic, per transcript line): "let's learn / study / talk about X", "next / now X",
   "what is X", "X is defined as / is called X", "types / kinds of X", "X is classified into A, B and C",
   "difference between A and B". Output: topic candidate, list items, comparison candidates.
3. **Provisional frame** (planner-owned, not LLM): on a topic cue the projector shows the title at once (faded
   "listening" state). The interpretation confirms or renames it; unconfirmed after N s → removed or kept as said.
4. **Live list**: after a list cue each spoken item is added to a provisional hierarchy / chips as heard; the LLM
   result replaces them in place (no jump).
5. **Gate**: a strong topic cue cuts the unit immediately (the previous tail goes as its own unit) → fixes A3; the
   wall-clock floor becomes token-aware (fires when TPM room allows; floor 8 → ~3–4 s, config), so a paid LLM later
   only needs a config change.
6. **Fallback** uses the cue detector for titles / lists (A4). `lecture_move` warning fixed (G2).
- Target: first visible change ≤ 2 s after a topic cue; speech → final slide median ≤ 6 s; tokens/min ≤ 1.5× baseline.

**S1 result (2026-10-16): implemented, tested, runtime-verified.**
- Code: `understanding/cues.py` (new), `ConceptSignal` cue fields, gate `announce` cut, service wiring, engine
  `CueSlide` / `CueList` (announced slide, live list, adopt / keep title / expire, earlier units hold the screen,
  late parts inserted behind their part), `SlideSpec.pending`, `HierarchyBlock.provisional`, display listening dots +
  faded tree, fallback names topics from cues / first defined term, config floor 4 s / max_wait 8 s / hold 4 s /
  max_words 32 / dwell 10 s. Tools: `tools/v1_eval.py` (+ `--replay`, `--gate`), `tools/screenshot_cues.py`.
- Tests: 35 cue unit tests (lines from tests 1–30), 10 engine cue tests; fast 598, browser 39 pass.
- Baseline (`verify_results/_eval/v1_baseline.json`, tests 1–30 as recorded): latency 10.1 s median / 20.2 s p90,
  announcement → title 17.2 s median, 36 of 93 never titled, part rate 0.70.
- Replay, recorded answers (0 tokens): announcement → title 15.0 → **0.64 s** median, p90 29.3 → 1.9 s, never
  38 → 4 of 95; test21 planets get their own slides (Mercury … Saturn) instead of "Planets" ×5.
- Gate replay (0 tokens): mixed-topic units 7 → 0; line wait 6.65 → 4.05 s median, p90 14.8 → 11.5 s.
- Live, simulated first 3 min of test3 (`tests/fixtures/lectures/f013_cues_chem.txt`, session 20261016-020439-4300,
  17 calls, 32.3k prompt tokens): speech → slide **6.0 s median / 11.1 s p90** (test3 recorded: 9.5 / 15.4 s), every
  announcement titled at once, "Momentum" (misheard) renamed "Matter" by the interpretation, 7 slides, 0 parts, no
  provisional leftovers. Not yet tried on the real mic.

**S1b result (2026-10-16): live as the teacher speaks — implemented, tested, runtime-verified on audio.**
User (2026-10-16): title the moment a topic is announced, the definition as it is said, every sentence evaluated,
list names appending as spoken; "do what's best… making it fast must not make it inaccurate".
- Speech: second model `distil-small.en` (own thread) transcribes the utterance in progress every 0.8 s
  (`TranscriptPartial`, agreed prefix only); no vocabulary prompt for it (the prompt made it ~10x slower). Sentence
  cuts from its word timings: lines become sentences without pauses (audio run: line median 9.7 → 4.0 s). Final text
  unchanged (medium.en + prompt).
- Understanding: `LiveCue` from the agreed live text, per sentence (`cues.detect_all`, `live_definition_any`), with
  the lecture time its sentence started. Gate: pause 1.2 → 0.6 s, floor 4 → 2 s (each finished sentence goes out).
- Presentation: announced title grows as said; faded definition card (`DefinitionBlock.provisional`) while the term
  is the slide's subject; live list; links to final lines by lecture time (utterance numbers shift with sentence cuts);
  real content of the same kind supersedes the faded one on its slide.
- Same WAV (`tests/fixtures/audio/f013_cues_chem.wav`, Windows TTS of the first 3 min of test3, 0.45 s gaps), per
  announcement, title on screen relative to the end of that sentence: S1 settings +4.4…+14.5 s → S1b **−2.1…−0.5 s**
  (before the sentence ends); definitions live −3.8 / −1.8 s, interpreted +4.9 / +5.9 s. Live pass 145 ms median.
  Slide structure the same in both runs (both fold Elements / Compounds into Pure substances → S2). Calls 11 → 17
  for 2.7 min (+55 % tokens). Sessions 20261016-032558-f162 (S1b), 20261016-033157-df56 (S1 settings).
- Bug found and fixed on the way: a faded list never linked to its final line made the slide overflow into a second
  part ("came to nothing" removal of a slide with content) → time-based linkage + supersede rule.
- Tests: fast 608 (+10 live / partial tests), browser 39. Not yet tried with a real microphone and a human speaker.

### S2 — Structure (B1–B6)
1. Interpreter returns **`parent`** (an outline node, or "new") + `subtopic`; code derives the relation and placement
   (sibling / child / new topic / revisit). Outline becomes a tree (≤ 3 levels, bounded tokens).
2. **Announced-children registry**: "X is classified into A, B" → A, B expected under X; when A starts, its parent
   is known without the model; the topic header follows the registry (B5).
3. **Novelty check before "part N"**: a new defined term / keyphrase cluster that is not the current subtopic opens
   a subtopic slide instead of a continuation (B1, B3).
4. **Revisit rule**: returning to an existing subtopic reuses its frame only when the keyphrases match; otherwise a
   new subtopic (B4).
- Check: boundary R on the 12 annotated lectures (replay rebuild + 3 short live slices), part-N rate, revisit errors.
- Target: boundary R ≥ 0.70 at P ≥ 0.78; part-N ≤ 45 %; sub_concept/child relations visible in Lecture Structure.

**S2 result (2026-10-16): structure. Implemented, unit-tested, replay- and live-checked. Recall and part-N targets
not met.**
| Replay of the 18 annotated lectures (recorded answers, 0 tokens) | before | after | target |
|---|---|---|---|
| boundary precision | 0.796 | 0.775 | ≥ 0.78 |
| boundary recall | 0.442 | 0.507 | ≥ 0.70 |
| F1 | 0.507 | 0.555 | – |
| "part N" rate | 0.733 | 0.619 | ≤ 0.45 |
| slides under a parent | 0 | 34 | visible |
(`tools/v1_eval.py --structure`; files `verify_results/_eval/s2_baseline.json`, `s2_replay.json`.)
- Built: the tree by code (see presentation.md "Structure"): numbered sections, announced member under the model's
  set, a registry of expected children, qualifier children (also under "X of Y"), member content gated by naming,
  lines before an announcement stay, confirmed new topic on the slide already titled by it, revisit guard in the
  interpreter, state outline tree and prompt outline children, crumb Topic — Parent, nested Lecture Structure in
  deck order.
- Item 1 (model `parent`): **rejected after its A/B** on gpt-oss-120b (test3 + test20, 12 units, 27,988 tokens).
  It gave no useful parent, lost "Intellectual Causes", and invented a "Diodes at Atomic Theory" subtopic. The rule
  stays in `prompt.py`, switched off.
- Item 3 (novelty before "part N"): a newly defined term as a new subtopic was tried and dropped. Most such terms are
  supporting terms ("Bolus", "SSID"), and precision fell. Only an absorbed facet that overflows gets its own title.
- Live check (`tests/fixtures/lectures/f013_s2_causes.txt`, test20 causes → stages as Whisper heard it, session
  20261016-122638-6e6a, 20 calls, 0 fallbacks, ≈ 47k tokens): Social (under "Causes of French Revolution") → Causes
  → Political Causes → Intellectual Causes → Stage 1 (I, II) → Stage 2. Political and Intellectual had no parent
  because of the "X of Y" form; fixed afterwards and covered by a unit test, but not re-run live.
- Why recall stays low: the model's subtopics are coarser than the annotators' (test15 keeps one subtopic for the
  whole lecture; web lectures are narrative with no cues), and test29 has fallback answers. This needs a model-side
  change, either a better model or S3 prompt work, and an A/B for it.
- Found and fixed on the way: "The third topic is Integral Calculus" shown as a bullet (announcement filter);
  "Statics" (Statistics misheard) placed as a member of "Measures of Central Tendency"; the Lecture Structure listed
  children after all of their parent's slides.
- Still open (S3): the model sometimes copies a transcript line verbatim as a point ("Economic, as a result of
  numerous wars wages by Louis XVI…", "Chantment among the masses…"). This was seen in the live run and in the
  recorded A/B answers.
- Tests: fast 626 (+18 in `tests/unit/test_structure.py`), browser 39; screenshots `tools/screenshot_structure.py`
  (test20, test21, both themes) looked at.

### S3 — Representation + truthfulness (C1–C9, E1–E2)
1. **N-way comparison**: schema `compare: [2–4 names]`, `rows: [{aspect, values[]}]`; comparison cue from S1 goes
   into the prompt as a hint; composer table 2–4 columns with headers, never empty; 3+ items stacked on narrow space.
2. **Definition card**: hide the term when it ≈ title (fuzzy); strip a repeated "Term:" prefix; a non-definition
   ("was discovered by…") becomes a point.
3. **Dedupe**: normalise spoken numbers / powers / units / symbols before the coverage guard and item merge.
4. **Garbage gate** for "shown as said" and notes: drop fragments, announcements, meta brackets, low-vocabulary lines
   (WordPiece-unknown ratio, no verb, < 5 content words).
5. **Lecture glossary**: outline + slide terms + study-material terms; deterministic phonetic / fuzzy match fixes a
   misheard term on the slide (logged `[HEARD]`), and the glossary goes into Whisper's prompt as the lecture grows.
6. **Formulas**: spoken subscripts (ν₀, λ₀, "nu naught") normalised in `mathtext`; equation lectures get the
   equation block.
7. **Layouts**: group cards for named groups, fact tiles for attribute lists, code block for spoken code, timeline
   keeps only dated events.
8. **Named equations (C10)**: when the teacher names a standard equation ("Schrödinger's time-dependent equation",
   "Maxwell's equations", "Gauss's law in differential form") or says "write / show the equation", the slide shows
   its standard form. Source order: (a) a local, checked library of standard equations (`presentation/equations`,
   LaTeX + symbol legend, name aliases incl. misheard forms, forms such as integral / differential), 0 tokens;
   (b) the teacher's own notes (F-012 passage with that equation); (c) the model's `standard_formula` for a named
   equation, marked as added and validated by KaTeX. /control gets **Show equation** (search the library / type a
   name) for an equation the teacher wants without saying its name. Several equations (Maxwell's four) = one formula
   group block, revealed one by one as each is named.
9. **E1**: an applied concern that changes no element → card says "the slide shows what you said" + Show correction.
   **E2**: prompt rule "never state a fact that was not said" + A/B.

**S3 result, group S3a (2026-10-17): deterministic representation fixes (items 3, 4, 2, 6, 7), 0 tokens.
Implemented, unit-tested, replay-checked, screenshots looked at.** User (2026-10-17): "do what's best" on the open
questions: keep the guard behind a gate; no unknown-word rule (see below); the code block moves to S3b with the schema;
signed numbers fixed now; a layout conversion needs at least two lines of the same shape.
| Replay of tests 1–30, recorded answers, guards re-run (`tools/v1_eval.py --s3`, 0 tokens) | before | after |
|---|---|---|
| slide items (points, notes, examples) | 1,468 | 1,370 |
| verbatim copies (≥ 8 words, ≥ 0.85 of a spoken sentence) | 187 (12.7 %) | 105 (7.7 %) |
| coverage-guard lines on the slides ("shown as said") | 118 | 33 |
| garbage lines (meta, spoken code, references, speaker asides, glued headings) | 31 | 10 |
| lines with a bare pronoun subject ("It can involve …") | 38 | 21 |
| duplicate items on a slide (quantities normalised) | 6 | 1 |
| definition cards that repeat the title, repeat their term or are no definition | 18 | 2 |
| formulas that do not render properly (Greek as text, "s i n", nothing) | 7 | 0 |
| unusable comparison tables (empty headings) | 2 | 2 (item 1, S3b) |
| boundary P / R / F1, part rate (18 annotated, `--structure`) | 0.775 / 0.507 / 0.555, 0.619 | 0.775 / 0.507 / 0.555, 0.613 |
(files `verify_results/_eval/s3_before.json` (S2 code), `s3a_replay.json`, `s3a_structure.json`; every flagged line is
listed with `--list`, and the before lists were checked by hand: 6 of 6 duplicates and 31 of 32 garbage lines real.)
- **Main finding:** the "verbatim bullets" of the S2 live run ("Economic, as a result of numerous wars …",
  "Chantment among the masses …") came from our coverage guard, not from the model; the model had paraphrased both.
  The guard's word match was too weak (no stemming: "masses" ≠ "Mass"; no quantities).
- **Item 3, dedupe:** `textutil.normalise_spoken` (powers, superscripts, "minus N", "into", unit words → symbols, only
  after a number or "per") and `textutil.stem`; used by the guard and by `composer.is_duplicate` / `_subsumed`. On a
  slide: a definition card replaces a shorter point of the same term (test28 "Convergent: …"); a fuller version of a
  point grows it in place, same id, when it adds ≥ 2 content words (test13, test27); a definition already shown as a
  point is not added; a "Label: names" point for an existing group card adds its names to the card.
- **Item 4, garbage gate** (`understanding/quality.py`): meta notes, spoken code, references to other lessons
  ("Recall that", "will be discussed in later chapter", "The third topic is …"), the speaker as subject ("You …", "We
  need …", "Imagine …"), a bare pronoun subject, headings glued to the sentence ("Economic, as …", "Doping a
  semiconductor One way …") and cut-off starts ("Will come out …", "Through …"). It filters the coverage guard and the
  empty-act filler; the fallback keeps the teacher's examples ("If you buy the book …") but drops the rest. Linking
  words are tidied away ("Thus,", "Recently,", "As a result,"; not "Generally,"). A line the model cited in a content act
  comes back only when ≤ 20 % of it is on the slide (≤ 34 % otherwise). Model notes lose "[unclear …, likely
  mis-heard]"; a concern whose "correction" is such a note is dropped (test6: applied, it replaced the teacher's words).
  Cost, checked by hand: of the 93 guard lines no longer shown, ~14 were real statements the model had cited and partly
  covered (e.g. test27 "The hacker verifies whether the identified vulnerabilities can actually be exploited …"), ~79
  noise, duplicates or announcements.
- **No unknown-word rule:** the MiniLM vocabulary lacks real words ("rioting", "buoyancy", "grievances") and splits
  "chantment" into real pieces; the transcript has only a segment confidence. Per-word Whisper probabilities fit item 5.
- **Item 2, definition cards:** the display hides the term when the title names it with plurals folded and a bracketed
  acronym ignored ("Atom" / "Atoms", "Operating System (OS)"); a repeated "Term:" prefix is removed; "was discovered …"
  becomes the point "Electron was discovered …"; a ";" list of short items is a list; a Greek symbol keeps its case
  (test15 showed "Ν" for ν).
- **Item 6, formulas** (`mathtext`): ν₀ / ν0 / "nu naught" → ν₀, λ_T, hν → h ν, sin / cos / tan / log as functions,
  a trailing "..." → ⋯, all Greek letters; "Δx", "ωt" stay products.
- **Item 7, layouts:** ≥ 2 "Label: names" points → group cards (test7 Central / Allied Powers); ≥ 2 short "Label: value"
  points, most with a number → fact tiles (test6); a classification of "Kind: what it is" points → member cards (test24
  topologies, test25 process states); an undated timeline event → a point. Code block: S3b.
- **Found beyond the list and fixed:** `content.clean` stripped a leading minus as a list dash ("-55 °C" → "55 °C",
  test5); an example tied to a definition card was drawn twice, under the card and in the aside (test3; slide.js and
  `composer._split`).
- Tests: `tests/unit/test_representation.py` (48, real lines from tests 1–30); fast 674, browser 39 (one run of three
  had 1 failure that did not repeat). Screenshots `tools/screenshot_s3.py`, both themes: groups (test7), facts (test6),
  members (test24), definition (test3), formulas (test15, test23).
- Still open from S3a: Jupiter / Saturn descriptions with ";" stay definitions (acceptable); a trailing single card
  still shows its term ("Atom" under "Atoms"); recall 0.507 unchanged (not a goal of S3a).

**S3 result, group S3b (2026-10-17): N-way comparison (item 1), glossary + Whisper prompt (item 5), named equations
(item 8). Implemented, unit-tested, replay-checked, A/B on gpt-oss-120b (34,808 tokens), screenshots looked at.**
User (2026-10-17) "do what's best" on the open questions. What that decided: the library only as the equation source
((b) notes skipped, since PDF text garbles equations; (c) the model's `standard_formula` goes to S3c with the E2 A/B).
A glossary fix only from trusted spellings. Code shown as heard only with ≥ 3 spoken symbols, then dropped after the
measurement (see below). The comparison-hint A/B was done in S3b.
| Replay of tests 1–30 (`tools/v1_eval.py --s3`, recorded answers, guards re-run, 0 tokens) | S3a | S3b |
|---|---|---|
| comparison tables / unusable (empty headings) | 6 / 2 | 5 / **0** |
| formulas on slides (of which a named standard equation) | 23 | 32 (9) |
| boundary P / R / part rate (`--structure`) | 0.775 / 0.507 / 0.613 | 0.775 / 0.507 / 0.615 |
(files `verify_results/_eval/s3b_replay.json`, `s3b_structure.json`.)
- **Item 1, comparison.** Schema `compare` (2–4 names) + `rows [{aspect, values[]}]`; the old `pairs {aspect, left,
  right}` is still read. `interpreter._normalise_rows` also accepts values keyed by the names and plain lists. Repairs in
  code (`content.comparison_pieces`):
  - cells "Name: value" name the columns (test18: ANN / TNN / RNN as one 3-way table);
  - one heading over rows that each name a thing are fact tiles under that heading (test5: mixture → −55 °C);
  - a row that only repeats the column names is dropped (test15).

  The composer places cells by column name, widens a table by one more compared thing (≤ 4 columns), fills a cell
  into the same aspect, and never draws a table without headings (rows without names become points). The interpreter
  takes the names from the unit's spoken cue when the model gave none (`_compare_from_cue`). The cue regex now
  allows "Now let's differentiate …" (test8 was missed). Prompt: line tag `(compares: A | B)` from the cue, and the
  N-way rule. **A/B** (`tools/prompt_ab.py --compare`, 9 units of test8 / test27 / test18 / test5, then the old prompt
  re-sent on the 3 units that differed): the new rule gave the test27 table, the correct 3-way test18 table, the test5
  facts and the test8 headings. The losses (test8#90, test18#13 comparison → points; test27#55 empty) happened with the
  old prompt too, so they are sampling variance. No new unsaid fact. **Live.** Tokens 20,604 + 7,450 + 6,754.
- **Item 5, glossary** (`understanding/glossary.py`, 0 tokens).
  - **Sources:** the setup and study-material terms (trusted spellings), plus each interpretation's titles, defined
    terms and compared names.
  - **Admission:** a lecture term needs all English words (wordfreq, local data; new dependency in `understanding`
    and `dev`). An acronym needs the lecture to spell it out. So "Wannesbord theory" and "TNN" are never admitted.
  - **Whisper prompt:** grows as the lecture does (`VocabularyChanged` → `SpeechPipeline.set_prompt`; the newest terms
    within 60 words). medium.en on the f013 WAV: 939 / 476 ms median with a 59-word prompt vs 1060 / 843 ms with the
    short one, i.e. no slowdown.
  - **Slide fixes, measured first** (replay, recorded answers):
    - With lecture terms as the source: 10 fixes, only 2–3 right ("Polydentate ligand" → "Monodentate ligand",
      "PMOS" → "CMOS", "Stichometry" → "Chemistry": real terms the word list lacks).
    - Acronyms with rhyming letter names gave "TNN" → "CNN" but also "GSAT" → "EMAC" from a datasheet.
    - **So:** fixes come only from trusted terms. A phrase must sound alike by phonetic key (≥ 0.7–0.8 by length) and by
      consonants (≥ 0.75), and its differing words must not be English. Acronyms are never fixed.
    - Replay with the current study-material terms: 1 fix ("photolytic" → "photoelectric", test15), and it is right.
      Each fix is a transcription concern, logged `[HEARD]`.
- **Item 8, named equations** (`presentation/equations.py`, 42 entries: quantum, Maxwell (differential + Gauss
  integral), mechanics, gases / thermo, chemistry, optics, maths, GDP).
  - **Rendering:** every entry renders in KaTeX in Edge (browser test), with its name and legend.
  - **Matching:** names are matched on the normalised line, Whisper spellings included. A family name shows its
    defaults (Maxwell → four, "equations of motion" → three, "Schrödinger equation" → time-dependent); a specific form
    named in the line wins. An ambiguous name needs its subject (continuity equation: fluid / flow).
  - **"Write the equation"** on a slide about one shows it.
  - **Engine:** reads `TranscriptFinal` and adds the standard form to the unit's pieces, once per lecture, and never
    when the unit has its own formula (what was said wins). `FormulaBlock.name` and `standard` show the name and a
    "standard form" tag.
  - **/control "Equation":** search via `/api/equations` and the `show_equation` command onto the live slide (its
    next part if full).
  - **Replay:** test16 now shows both Schrödinger forms (it showed nothing). Also test1 Newton 2/3, test2 continuity
    + Bernoulli, test15 Planck, test29 GDP, test30 Ohm.
  - **Layout:** a set of 3+ formulas renders in two columns, with an odd last card spanning both and one legend
    (composer `FORMULA_GRID_MIN`). Stacked, Maxwell's four fitted only 2 per slide.
- **Code block (C8): not built.** Spoken Verilog converted as heard (test26) is unreadable ("square bracket 3 is 2 0
  square ) count", "If (, reset ) count <= 4", "Always add the red" for `always @(`). The model's prose bullets are
  better. The copied bullet "Single inverted comma b1 semicolon …" is already gated (S3a). A code field filled by the
  model belongs to the S3c prompt work.
- **Tests:** +32 in `tests/unit/test_representation_s3b.py` (real lines); browser +1 (library in KaTeX). Fast 706 and
  browser 40 pass (see STATE for the last run). Screenshots `tools/screenshot_s3.py compare3 tiles named_eq maxwell
  motion`, both themes, plus /control Equation search ("maxwell"), all looked at.
- **Still open:**
  - test18's 3-way table is titled with the misheard "TNN"; it stays a second table beside "CNN | RNN", since an
    unadmitted acronym cannot be fixed.
  - test15 shows "Kinetic energy: blue Lower | green Higher", reversed from what was said; this is the model's (E2,
    S3c).
  - A Whisper prompt that lists terms can be echoed in a garbled chunk (seen once on fixed 8 s chunks: "The first term,
    the second term …"); this needs a real-mic check.

**S3 result, group S3c (2026-10-17): truthfulness (item 9) + user requests of 2026-10-17 (performance mode, start
card, Follow). Implemented, unit-tested, replay-checked, A/B on gpt-oss-120b (31,338 tokens), screenshots looked at.**
User (2026-10-17) "do what's best" on the open questions: Show correction replaces a reworded item; no model
`standard_formula` (4 missing equations in 30 lectures, all library entries now); no model code field; no word-overlap
"added" flag; A/B budget ~30-40k. Also asked: fix the start card (image copy 2.png), remove or fix Follow, and a switch
between high performance and a standard mode that uses fewer tokens.
- **E1, what the slide shows for a concern** (engine `slide_version`, `CorrectionPlaced`, card + terminal). Measured
  first (replay of tests 1–30, 286 concerns with wrong/right): 134 switched, 62 already rewritten correctly by the
  model, 73 not on the slide, 8 "wrong words kept" by a word check, all 8 correct rewordings by hand; every one of the
  152 unswitched said "slide shows the correction". After: factual cards 14 correction, 8 "states it correctly", 6
  "not on the slide", 1 "shows what you said" (test13's counterfactual "if the brain were fully suspended …", false,
  the teacher keeps it). A reworded item (points, card notes) gets the corrected statement on Show correction and its
  text back on Show what I said; the heart lecture's case is a unit test.
- **E2, facts not said.** Hand check of 49 items flagged by word overlap (2,135 items): most were said in the next
  lines or were correct repairs of misheard words; real cases: test4 alpha scattering, test6 "began on 6 April",
  test10 a finished cut-off line, test15 the reversed table. So no overlap filter. Built:
  - prompt rule `SAID_RULE` (+74 tokens per call), **live**. A/B (`tools/prompt_ab.py --said`): 5 units vs recorded
    answers, 3 with both arms resent (sessions with a REFERENCE passage do not rebuild exactly), 2 old-prompt resends.
    Better: test4 (no alpha scattering), test30 (no added "octet rule" name), test15 (keeps the said reason). Same:
    test6 (6 April with both), test11 (the old prompt did not invent this time). Worse in form: test8 and test10 copied
    the cut-off line ("… as the output of", "deals with the internal"), test27 one shorter point. Truthfulness: 2 unsaid
    facts gone, 0 added, so it ships; test8's invented RNN definition stays with both prompts.
  - `interpreter._drop_cut_off`: items ending in a lower-case function word leave the slide (1 of 2,050 recorded
    items: "Each dipole has an"; the A/B's "… as the output of").
  - `interpreter._comparison_direction` (`spoken_order`): a two-way row of bare comparatives that contradicts the lines
    is swapped; tests 1–30: only test15 changes, correctly.
- **Equations:** library 48 entries (+ Pascal's law, Kirchhoff's current / voltage laws and family, straight line,
  heard "Kjotch's law" / "O'Hams law").
- **Performance mode** (`app/modes.py`, `[performance]` config, `set_mode`, `ModeChanged`, data/preferences.json,
  `--mode`). Measured first: S1b's extra calls come from the sentence cuts + 0.6 s pause + 2 s floor (same 2.7-min WAV:
  16 vs 11 recorded calls; the gate replay of tests 1–30 changes little because those lines were not cut). **Standard**
  (default) = the S1 settings (utterance lines, 1.2 s, 4 s); **High performance** = the S1b settings. Both keep the
  instant display of the live speech model (0 tokens). Switch on the start card (Speed) and as a top-bar pill.
- **Start card** (F5, F6 from S4): one Study material row + picker (search, ticks, Add file, Add web link); the card's
  column is `minmax(0, 1fr)` (a long name had pushed the fields past its edge); with 15 files it stays inside the
  preview (browser test). Web pages without a `<title>` are named "Human Brain · byjus.com".
- **Follow removed** (F4, user: it turned pages early and back): service, UI, events (`notes_follow` still decodes in
  old logs), tests; the embedder still indexes the study material.
- Tests: +11 `tests/unit/test_truthful_s3c.py`, +7 `tests/unit/test_modes.py`, notes tests rewritten (the lecture never
  turns the page), browser: picker + 15 files + Speed / pill, notes turned by hand. Screenshots: `screenshot_s3.py
  cards`, `artifacts/reference/start_card_*`, `mode_pill_high.png`, both themes.

### S4 — Images + UI + robustness (D1–D4, F1–F6, G1)
1. Images: image need also from the subject + slide type (concrete / process / apparatus); one image per deck used
   once unless the teacher repeats it; captions = cleaned figure caption ("Figure 3.1: …") or the query, never page
   text.
2. Own PDFs (STM32): vector-figure clusters (`get_drawings`-style path regions) rendered as figures; caption =
   "Figure N.N" line only; screenshot class skips the CLIP photo gate and uses label match + text-on-figure match.
   Verified on the user's STM32 / ESP-WROOM PDFs in `data/notes`.
3. UI: ~~remove Follow~~ (done in S3c); fixed-ratio notes page box; drag depth counter; tabs collapse by width
   (container query); ~~start card picker, web pages named by title~~ (done in S3c).
4. G1: disk-full handled (warn at start when < 1 GB, no traceback; event log keeps running in memory).

### S5 — Wrap-up
Full suites (fast, slow, browser), `v1_eval` vs baseline, two live mic lectures by the user (one with a comparison
and a classification), screenshots, docs (understanding, presentation, display, visuals), STATE, git checkpoint.
