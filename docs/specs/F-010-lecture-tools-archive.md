# F-010 — Lecture tools + past lectures (V2 group B)

Status: done (2026-10-07), verified — see STATE.md. User decisions: 2026-10-07 (answers to the group B questions).

## Goal
Everything is made only when the teacher asks, from one **Materials** card in /control, at any time (no need to end
the lecture), from this lecture and/or past lectures. Past lectures stay on the laptop and can be opened again in
/control (slides + the materials made from them).

## What the teacher can make (multi-select, one Create button)
| Item | Output | How | LLM |
|---|---|---|---|
| Summary slide | a slide on the projector, shown at once | teacher picks **This topic** (short, 3-5 points) or **Whole lecture** (complete, per topic) | 1 call |
| Key concepts slide | a slide on the projector | 5-10 terms + one-line meaning from what was taught | 1 call (shared with the notes) |
| Notes PDF | study notes | per topic: written explanation (LLM, from what was taught) + the slides' own definitions, formulas (KaTeX), steps, tables, trees, examples, images; key-concepts glossary at the end | 1 call per ≈1.8k tokens of lecture, + key concepts |
| Assignment PDF | theory questions | count chosen (default 10), short + long answers, marks; no answer key | 1 call |
| Slides PPTX | the deck as on the projector | **Light or Dark** chosen in the card; each slide rendered by the real slide renderer in headless Edge: background (cards, formulas, images, arrows) as a picture, every plain text as an editable text box at its exact place, font, size and colour | 0 |

No transcript export (user). "From what I teach" (user): the material is the lecture's slides (what the projector
showed, teacher edits included) plus the transcript of each topic; the LLM never adds facts that were not taught.

## Scope: which lectures
The card has a **From** row: *This lecture* (default) + any past lectures picked from a list. A topic summary always
uses the live slide's topic of this lecture. With several lectures the content budget is split between them.

## Names
Every file gets an automatic name (`Photosynthesis - Notes - 7 Oct 2026.pdf`); the name field is editable before
Create and the file can be renamed later. Downloads use that name.

## Students
PDFs are shared on the student link (/view → a Materials button → download) unless the teacher turns sharing off for
that file. PPTX and slides stay with the teacher.

## Past lectures
A **Lectures** tab lists past lectures (title, date, slide count, minutes) newest first, rebuilt from each session's
event log (`SlidePatch` + `DeckState` + `TranscriptFinal`), cached in `data/sessions/<id>/lecture.json`.
Sessions without a content slide are not listed; the teacher can hide a lecture from the list (nothing is deleted).
Opening one shows its slides full size in a viewer over /control (arrows, slide strip) and the materials made from it
(open / download). "Make materials" from there preselects it in the Materials card.

## Architecture
```
/control Materials card → command materials_create {items, lectures, include_current}
   MaterialsService (one job at a time) ─ archive.LectureArchive  (past + current session → LectureRecord)
                                        ─ content.lecture_topics (slides + transcript per topic, bounded)
                                        ─ writer.*  (bounded prompts → LLMRouter → strict JSON → one repair)
                                        ─ render.*  (HTML → headless Edge via our own server → PDF / PPTX)
                                        ─ Deck.present(spec)   (summary / key-concepts slides)
   MaterialsState (ephemeral) → hub → control only
HTTP: GET /api/lectures, GET /api/lectures/{id}, GET /api/materials/{id}/file (teacher, or anyone if shared PDF),
      GET /api/shared (student list)
```
- `data/materials/index.json` + `<id>.pdf|.pptx`.
- LLM: every prompt bounded (≤ 2.6k tokens in, cap out), never the whole transcript; per-call timeout longer than the
  live interpretation's (writing takes longer); failure → the item fails with the reason (no made-up content).
- Without the LLM (`--no-understanding`, every key spent): the PPTX still works; LLM items say why they cannot run.
- Summary slides: added at the end of the deck and shown (`Deck.present`); the lecture's next new slide follows as
  usual.

## Fixes from the group A review (user 2026-10-07)
- Dark-slides button: a filled crescent instead of the outline moon (the light-theme sun stays).
- Notes picker: the native select with "+ Add another PDF" replaced by a menu in the app's style.
- Empty notes card: minimal (icon, Add PDF, one short line).

## Tests
- unit: archive rebuild (order, latest versions, removed slides, title, junk filter, cache), content topics +
  transcript assignment, prompt budgets, writers with a fake router (valid JSON, repair, failure → error, count),
  materials store (names, rename, share, remove), summary / concepts slide specs, service jobs end to end with a fake
  router, server routes (teacher only, shared PDF public, unshared 403).
- browser: PDF + PPTX rendering (real Edge, file opens, text boxes present at the rendered positions), /control
  Materials card + Lectures viewer, student Materials list.
- runtime: recorded sessions at 0 tokens (`tools/materials_dry.py` prints every prompt and its size), then one small
  live Groq run; PPTX checked by exporting it through PowerPoint to PNG and looking at it.
