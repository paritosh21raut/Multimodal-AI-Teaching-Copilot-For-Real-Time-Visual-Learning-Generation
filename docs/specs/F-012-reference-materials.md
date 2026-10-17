# F-012 — Reference materials (V2 group D)

Status: implemented, tested, runtime-verified (2026-10-12), except speech terms (not tried on real audio) and quiz
fact-checking (see Verification). User decisions: 2026-10-12 (answers to the 14 doubts).

## Goal
The teacher's **My Notes** files (PDF, Word, PowerPoint, text, images, web links: everything F-009 / F-010b take) are
also the lecture's **reference material**. A local index (MiniLM, 0 tokens) is kept apart from the live transcript
and is used only to make what the teacher says show up more accurately. The lecture never depends on it, and it never
adds content the teacher did not teach. All My Notes features stay as they are (following the slides was removed later, F-013) and
projecting a page.

## What is indexed (`notes/reference.py`, under `data/notes/<id>/`)
| Part | How | Cache |
|---|---|---|
| Text chunks | page texts → 60-word chunks (the notes-follow chunker) → MiniLM | `ref-chunks.npz` |
| Figures | pypdfium2 image objects: not page backgrounds (≥ 85 % of the page, or the same image on ≥ 3 pages), ≥ 12 % of the page width and ≥ 140 px; the **page region is rendered** so labels drawn over a figure stay; label = caption / text around it + the page's first line + the file name. An image file the teacher added = one figure labelled by its name | `figures.json`, `f<n>.png` |
| Terms | words of the active files that MiniLM's WordPiece vocabulary does not know (`GPIO`, `NVIC`, `chlorophyll`), seen ≥ 2 times | computed on demand |

- Built in the background once per file (content hash), after it is added or when the matcher model is ready.
  Progress shows in My Notes. Removing a file removes its index.
- **Active set**: each file has *Use for lectures* (on by default; ≤ 10 files on at a time), saved in
  `data/notes/index.json` and kept for the next lecture. Each file also has *Private*: never sent to the LLM (off by
  default). It still helps images and speech recognition.

## Where it is used
| Use | LLM | Rule |
|---|---|---|
| Speech recognition | no | ≤ 30 terms are added to Whisper's initial prompt ("Terms: …"), fixed at the start of the lecture |
| Slide images | no | For each image request, the teacher's figures come first: label ↔ query (MiniLM ≥ `FIG_LABEL_MIN`), then the CLIP gate. Accepted → `source = "reference"`, title `<file> p.N`. Nothing accepted → Wikipedia / Commons as before |
| Live slides | yes | One `REFERENCE` block (best chunk(s), ≤ 150 tokens, only when cosine ≥ `SNIPPET_MIN` to the new lines + current slide), outside the 1200 dynamic room. Rule in the block: only to state / spell exactly what the lines say; never add from it; a line that contradicts it → factual concern. The block costs nothing when nothing matches |
| Concern card | — | A factual concern raised with a reference in the prompt carries `ref = "<file> p.N"`; /control shows "Your reference: …" |
| Quiz / test | yes | *Check facts with My Notes* (on by default): ≤ 400 tokens of chunks matched to the **taught** subtopics (cosine ≥ `GROUND_MIN`), labelled "for checking facts only". Guard: a question whose correct option's content words are not in the taught text but are in the reference is dropped as untaught (the repair asks again; a short set is an error, as before) |
| Lecture materials (summary, notes, assignment) | — | **Not used.** Their output has no single answer that a guard can check, so they stay taught-only (user: "if unable, only use lecture teaching") |
| Topic / outline understanding | — | not used |

Without an LLM, speech terms and images still work, and the LLM uses are skipped.
Students never see a reference file. A page reaches /display and /view only when the teacher projects it (F-010b).

## UI
- My Notes: each file in the file menu gets two toggles, *Use for lectures* (book) and *Private* (lock). The bin stays.
  The note line under the page says "Indexing <file> n %", "Used for the slide: <file> p.N" or how many files are in use.
- Start card: a **Study material** row (open-book icon) with chips for the files in use (× = stop using it) and
  *+ Add*, which takes the same upload as My Notes.

## Limits
≤ 50 MB per file (as notes), ≤ 600 pages (as notes), ≤ 10 active files, ≤ 20 000 passages in use (a 600-page book is
about 8000; past the limit a file is skipped and logged), ≤ 40 figures per file.

## Thresholds (real MiniLM / CLIP on `tests/fixtures/notes/reference_biology.pdf`, `test_reference_real.py`)
| | Related | Unrelated | Used |
|---|---|---|---|
| Passage ↔ lines (`SNIPPET_MIN`) | 0.68–0.81 | < 0.08 | 0.5 |
| Figure label ↔ query (`FIG_LABEL_MIN`) | 0.59–0.82 | ≤ 0.47 ("plant cell" ↔ chloroplast) | 0.5 |
| CLIP of the matched figure | 0.29–0.34 | other figures 0.19–0.28 | 0.22 (as web images) |

## Verification (2026-10-12)
- Tests: `tests/unit/test_reference.py` (17), `tests/integration/test_reference_real.py` (17, slow),
  `tests/e2e/test_reference_browser.py` (Edge). The fixture is built by `tools/make_reference_fixture.py`: real cached
  Wikimedia figures with captions, printed by Edge.
- Dry run, 0 tokens (`tools/reference_check.py`, 3 recorded lectures, 197 units): 12 units got a passage, all on
  topic (the photosynthesis units of the multi-topic lecture only). It cost +10 prompt tokens per unit on average.
  Two image requests of the human-body lecture were answered by the teacher's figures.
- Live (simulated heart lecture, temporary data folder):
  - 3 of 3 interpretations got the heart passage.
  - The "three chambers" mistake raised a factual concern that cites `reference_biology.pdf p.1`.
  - The slide image was the teacher's labelled heart diagram (0.1 s, no web).
  - 6,937 tokens.
- Quiz live (2 small sets, 1,645 tokens):
  - No question came from the reference alone.
  - The taught slide kept the wrong "one ventricle" fact (see STATE known issue: a pre-existing applied-concern bug),
    and the model still asked about it although REFERENCE said otherwise. Fact-checking a wrong taught fact through
    the prompt is **not reliable**. The prompt now says no question on a contradicted point; the root fix is the slide
    bug.
