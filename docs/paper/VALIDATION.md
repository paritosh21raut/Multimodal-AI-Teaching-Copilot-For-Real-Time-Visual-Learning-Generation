# Paper validation — test campaign (start here in a new session)

Purpose: produce the held-out results the IEEE paper still lacks (reviewer + professor: "feasibility, not quality").
Paper: `paper/IEEE_Paper_v2_draft.docx/.pdf` (6 pages, exact), sources `paper/build/src/`. Every `‹…›` placeholder
in the paper is filled from the data collected here. Paper rules: memory `paper-revision`, `docs/STATE.md`.

Temporary code for this campaign: `tools/eval_test.py` (recorder), `tools/paper_eval.py`, `tools/baseline_llm_slides.py`.
They are evaluation tools only; the app itself is unchanged. Remove or keep after the paper is submitted.

## Status (update this table as phases finish)

| Phase | Who | Status |
|---|---|---|
| 1. User's live tests `test1…test25` (own + other speakers) | user | **in progress** — not started 2026-10-11 |
| 2. Internet lecture recordings `web1…webN` | Claude, when the user says so | waiting for phase 1 |
| 3. Annotation sheets + teacher rating form | Claude prepares, user + co-author annotate, T1–T3 rate | waiting |
| 4. Final results → paper placeholders, rebuild, check 6 pages | Claude, when the user says so | waiting |
| Quiz / test feature (group C, F-011) | user builds before submission | not built (paper says implemented) |

## Phase 1 — user's tests (test1 … test25)

Run each test through the recorder instead of plain `python -m copilot`:

```bash
.venv/Scripts/python tools/eval_test.py run --note "self, physics, laptop mic"
.venv/Scripts/python tools/eval_test.py run --note "friend A, biology" -- --subject Biology
.venv/Scripts/python tools/eval_test.py list          # what is recorded so far
```

It starts the app exactly as usual (QUOTA → READY → Enter → live → `q` + Enter), picks the next free name
(`test1`, `test2`, …; `--name test7` to force one) and when the app ends writes:

```
verify_results/testN/
  terminal_log.txt   everything the terminal showed
  meta.json          name, note, session id, date, minutes, utterances, slides, theme, args
  transcript.txt     transcript as heard, with start times
  slides/NN.png      every final slide, real display, 1920x1080, the lecture's theme
  slides.md          same slides as text (used for annotation and the rating sheet)
  session/           session.sqlite (full event log) + lecture.json — the source of ALL numbers
```

If a run crashed or the folder is incomplete: `tools/eval_test.py export testN <session_id>` rebuilds it from
`data/sessions/<session_id>` (zero tokens). Extra screenshots the user takes can be dropped into the same folder.

Protocol (keep tests comparable):
- 8–15 min each, one topic per test, real teaching style (examples, asides, corrections are fine).
- Mix subjects (physics, chemistry, biology, maths, CS, geography/history, …) and **speakers**: at least ~10 of
  the 20–25 tests by people other than the authors (D1 was spoken by the authors; this is the main reviewer gap).
- Write the speaker as an anonymous label in `--note` (`self`, `speaker B`, …) — never a real name.
- **Do not edit, delete or reorder slides during a test** (navigation, pause, theme are fine). The results measure the
  system alone; if something was edited, say so in the note.
- Free quota: ~15–20 lecture min per key and model per day; check the `[QUOTA]` line before starting.
- Units that fell back (no LLM answer) are kept; they are reported separately.

## Phase 2 — internet lecture recordings (web1 … webN), Claude runs these

When the user says phase 1 is done (or asks earlier), Claude:
1. Picks 4–6 openly licensed lectures that suit a live classroom (single teacher speaking, school/early-college
   level, 8–15 min clip): NPTEL (CC BY-SA), MIT OpenCourseWare (CC BY-NC-SA), Khan Academy only if licence allows.
   Different speakers/accents than the tests. Record URL, licence, clip start/end in `meta.json` `note`.
2. Downloads audio (yt-dlp into `.venv` if needed; downloads in their own folder under `artifacts/web_audio/`, never run),
   converts with ffmpeg: `ffmpeg -i in.m4a -ss <start> -t <dur> -ac 1 -ar 16000 webN.wav`.
3. Runs at real time through the real audio pipeline, real STT and real LLM:
   `.venv/Scripts/python tools/eval_test.py run --source web --note "<url>, <licence>, <clip>" -- --audio-file artifacts/web_audio/webN.wav --no-wait --no-open`
4. Reports tokens spent (budget for the whole campaign ≈ 150–250k tokens, agreed).

## Phase 3 — annotation and teacher ratings

Claude generates (from `transcript.txt` / `slides.md` of every test):
- **Annotation sheet** per test: numbered transcript units; annotators mark topic boundaries and list key facts.
  Two annotators (user + co-author) work independently → Cohen's κ.
- **Rating form**: ~30 slides sampled at random across tests (fixed seed, stratified by subject and speaker), shown
  as `slides/NN.png` with the transcript span they came from. T1, T2, T3 (teachers **not** involved in development
  and **not** co-authors) rate 1–5: correctness, relevance, readability, usefulness. Names are never recorded.
- Annotation also marks unsupported statements (slide text not backed by the transcript) for Table III's
  "Unsupported" column (chemistry + biology baseline vs copilot) and Table IV.

## Phase 4 — final results (when the user asks)

From `verify_results/test*/session` + `web*/session` + the filled sheets:
- D2 size: N lectures, M minutes, K speakers; slides, LLM vs fallback units, tokens.
- End-to-end latency on D2: `tools/paper_eval.py latency <sessions…>`.
- Boundary F1 (±1 unit) and P_k, key-fact coverage, unsupported rate, κ, mean T1–T3 ratings (Table IV),
  LLM-only and fallback units reported separately.
- Optionally the LLM-controlled baseline on 1–2 D2 lectures: `tools/baseline_llm_slides.py <session> [--metrics]`.
- Fill every `‹…›` in `paper/build/src/body.py` / `content.py`, rebuild, render, **confirm exactly 6 pages**:
  `PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/build_docx.py paper/IEEE_Paper_v2_draft.docx`
  then `powershell -File paper/build/src/render.ps1 <docx> <pdf>` (prints the page count). Space left ≈ 6–8 lines of results text.
- Fig 5 keeps 9–12 slides; no "we/our"; T1–T3 only.

## Test log (append one line per test; `eval_test.py list` shows the same from meta.json)

| Name | Speaker | Subject | Min | Slides | Notes |
|---|---|---|---|---|---|
