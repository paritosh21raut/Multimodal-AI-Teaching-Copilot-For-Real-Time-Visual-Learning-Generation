# Paper validation — test campaign (start here in a new session)

Purpose: produce the held-out results the IEEE paper still lacks (reviewer + professor: "feasibility, not quality").
Paper: `paper/IEEE_Paper_v2_draft.docx/.pdf` (6 pages, exact), sources `paper/build/src/`. Every `‹…›` placeholder
in the paper is filled from the data collected here. Paper rules: memory `paper-revision`, `docs/STATE.md`.

Temporary code for this campaign: `tools/eval_test.py` (recorder), `tools/eval_sheets.py` (annotation + rating sheets,
scoring), `tools/paper_eval.py`, `tools/baseline_llm_slides.py`.
They are evaluation tools only; the app itself is unchanged. Remove or keep after the paper is submitted.

## Status (update this table as phases finish)

| Phase | Who | Status |
|---|---|---|
| 1. User's live tests `test1…test30` | user | **done 2026-10-15** — 30 tests, 349 min, 453 lecture slides (log below) |
| 2. Internet lecture recordings `web1…web6` | Claude | **see log below** (MIT OCW + NPTEL, 10 min each, run 2026-10-15) |
| 3. Annotation sheets + teacher rating form | Claude prepared 2026-10-15; user + co-author annotate, T1–T3 rate | **done 2026-10-15** — 18 lectures annotated by A and B, 5 raters T1–T5 returned; `score` run |
| 4. Final results → paper placeholders, rebuild, check 6 pages | Claude | **done 2026-10-15** — `paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot.docx/.pdf`, exactly 6 pages, no `‹…›` left; numbers and sources in "Phase 4 — final numbers" below |
| Quiz / test feature (group C, F-011) | user | built (commit 2150e77); paper describes it, no results |

## Automatic results so far (2026-10-15, zero tokens; human-judged numbers come in phase 4)

| | Lectures | Min | Lecture slides | Units (fallback) | Prompt tokens |
|---|---|---|---|---|---|
| Recorded (test1–30, six speakers) | 30 | 349.2 | 453 | 1275 (59) | 2.50 M |
| Public (web1–6, MIT OCW, NPTEL) | 6 | 60.0 | 52 | 344 (13) | 0.66 M |
| **D2 total** | **36** | **409.2** | **505** | **1619 (72)** | **3.16 M** |

End-to-end speech→slide latency per transcript line (`paper_eval.py latency … --out verify_results/_eval/e2e_d2.json`):
D2 all lines n = 2783, median 11.2 s, p95 53.0 s (LLM lines: 11.2 / 49.3 s; fallback lines: 12.4 / 69.7 s);
STT median 0.68 s, LLM call median 1.93 s. Web lectures: web1/2/3/5 median 10–12 s, p95 22–29 s; **web4 and web6 had
provider failures during the run** (web4: 32 failed calls, mostly connect timeouts; web6: 6, incl. 429 rate limits),
so their queues grew (median 67 s / 48 s). Report as recorded, with the cause; D1 (paper so far) was 12.5 / 36.8 s.
Phase 2 cost ≈ 0.66 M prompt tokens (free Groq tier) — above the 150–250 k first planned, because a live lecture
costs ≈ 11 k prompt tokens per minute; no paid API used.

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

## Phase 3 — annotation and teacher ratings (prepared 2026-10-15)

`.venv/Scripts/python tools/eval_sheets.py sheets` wrote (zero tokens; existing filled workbooks are never overwritten):

```
verify_results/_eval/
  annotation/A/<lecture>_A.xlsx   annotator A (user)        18 lectures: test3 10 14 15 17 20 (speaker A),
  annotation/B/<lecture>_B.xlsx   annotator B (co-author)   test21 22 23 24 25 29 (speaker B), web1–web6
  rating/rating_form.html         30 slides (10 speaker A, 10 speaker B, 10 web; seed 2026), one file, offline
  rating/rating_key.json          which lecture / slide / transcript span each form item is (do not send to raters)
  rating/returned/                put the raters' ratings_T1.csv, ratings_T2.csv, ... here
```

Annotators (each workbook has an Instructions sheet; A and B work **independently**, no discussion until both finish):
1. Transcript sheet, before looking at the slides: `1` in *New topic?* where a new topic/subtopic starts (where a
   teacher would start a new board/slide), and *Key fact* in the row where a key fact is said (≈1 per minute).
2. Then open `verify_results/<lecture>/slides/` and fill *On slides?* (Y/P/N) for every key fact.
3. Slide statements sheet: *Supported?* Y/P/N (did the teacher say it) and *Wrong?* `1` if factually wrong.
Effort ≈ 190 lecture minutes per annotator (≈ 3–4 h).

Teacher raters T1–T3 (not developers, not co-authors; names never recorded): send them only `rating_form.html`.
They open it in any browser, choose their code (T1/T2/T3), rate 30 slides 1–5 on correctness, relevance,
readability, usefulness, press *Download my ratings* and send back `ratings_Tn.csv` (≈ 30–40 min each).
Progress is kept in the browser; *Clear all answers* resets it for the next teacher on the same computer.

`tools/eval_sheets.py score` then computes everything for Table IV (see phase 4). It was tested on dummy-filled
copies (boundary P/R/F1 ±1 utterance, P_k, coverage, unsupported, wrong, κ, rating means + ICC(2,1)).

System boundaries = utterance whose interpretation opened a new content slide still in the final deck (overflow
parts with the same facet are not boundaries; end-of-lecture "Summary / Key concepts" slides are excluded).

## Phase 4 — final results (when the user asks)

From `verify_results/test*/session` + `web*/session` + the filled sheets:
- D2 size: N lectures, M minutes, K speakers; slides, LLM vs fallback units, tokens.
- `tools/eval_sheets.py score` → `verify_results/_eval/results.json`: dataset size per group, boundary F1 (±1
  utterance) and P_k, key-fact coverage, unsupported + wrong rate, κ (boundaries, supported), T1–T3 means + ICC (Table IV).
  LLM-only and fallback units reported separately.
- Latency on D2 without touching the D1 figure data: `tools/paper_eval.py latency test1 … web6 --out verify_results/_eval/e2e_d2.json`
  (without `--out` it overwrites `paper/build/fig/e2e_latency.json`, the D1 data used by `sessions_stats.py`).
- Optionally the LLM-controlled baseline on 1–2 D2 lectures: `tools/baseline_llm_slides.py <session> [--metrics]`.
- Fill every `‹…›` in `paper/build/src/body.py` / `content.py`, rebuild, render, **confirm exactly 6 pages**:
  `PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/build_docx.py paper/IEEE_Paper_v2_draft.docx`
  then `powershell -File paper/build/src/render.ps1 <docx> <pdf>` (prints the page count). Space left ≈ 6–8 lines of results text.
- Fig 5 keeps 9–12 slides; no "we/our"; T1–T3 only.

## Test log (generated 2026-10-15 from meta.json + session logs; `eval_test.py list` shows the same)

Speaker labels: the notes only distinguish **speaker A** (written "self") and **speaker B** (another person). Real names
were replaced by labels on 2026-10-15. If other people spoke some of the "self" tests, relabel them in `meta.json`
(`speaker`, `note`) as speaker C, D, … and rerun `eval_sheets.py score`.

| Name | Speaker | Subject | Min | Lecture slides | Units (fallback) | Notes |
|---|---|---|---|---|---|---|
| test1 | speaker A | physics | 3.9 | 6 | 20 (0) |  |
| test2 | speaker A | physics | 2.9 | 6 | 15 (0) |  |
| test3 | speaker A | chemistry | 11.3 | 16 | 47 (0) | annotated |
| test4 | speaker A | chemistry | 7.7 | 14 | 35 (0) |  |
| test5 | speaker A | chemistry | 8.0 | 11 | 31 (0) |  |
| test6 | speaker A | history | 2.6 | 5 | 9 (0) |  |
| test7 | speaker A | history | 5.8 | 6 | 37 (0) |  |
| test8 | speaker A | AI/ML | 30.9 | 37 | 106 (0) | 1 item deleted by teacher |
| test9 | speaker A | biology | 4.4 | 4 | 12 (0) |  |
| test10 | speaker A | biology | 14.6 | 19 | 54 (1) | annotated |
| test11 | speaker A | biology | 4.4 | 8 | 18 (0) |  |
| test12 | speaker A | biology | 9.5 | 7 | 24 (0) | 1 item deleted by teacher; rebuilt export 2026-10-15 |
| test13 | speaker A | biology | 17.1 | 15 | 42 (1) | rebuilt export 2026-10-15 |
| test14 | speaker A | AI/ML | 16.0 | 10 | 22 (0) | annotated |
| test15 | speaker A | physics | 10.5 | 15 | 43 (0) | annotated; session copy re-taken 2026-10-15; app not ended cleanly |
| test16 | speaker A | physics | 2.3 | 4 | 12 (0) |  |
| test17 | speaker A | physics | 6.5 | 7 | 23 (0) | annotated |
| test18 | speaker A | AI/ML | 4.0 | 8 | 17 (0) |  |
| test19 | speaker A | chemistry | 11.6 | 19 | 45 (0) |  |
| test20 | speaker A | history | 6.9 | 10 | 32 (0) | annotated |
| test21 | speaker B | physics | 8.4 | 12 | 36 (0) | annotated |
| test22 | speaker B | geography | 9.4 | 18 | 42 (0) | annotated |
| test23 | speaker B | maths | 13.8 | 31 | 73 (0) | annotated |
| test24 | speaker B | networking | 11.5 | 16 | 42 (0) | annotated |
| test25 | speaker B | operating system | 8.9 | 17 | 39 (0) | annotated |
| test26 | speaker B | VLSI | 16.0 | 20 | 52 (0) |  |
| test27 | speaker B | hacking | 25.8 | 29 | 72 (0) | app not ended cleanly |
| test28 | speaker B | geography | 15.9 | 23 | 61 (5) |  |
| test29 | speaker B | economics | 13.6 | 13 | 52 (52) | annotated |
| test30 | speaker B | physics | 45.0 | 47 | 162 (0) |  |
| web1 | web | biology | 10.0 | 10 | 45 (0) | annotated; MIT OCW 7.016 Introductory Biology F18, lec 11 'Cells, the Simplest Functional Units' |
| web2 | web | chemistry | 10.0 | 9 | 46 (0) | annotated; MIT OCW 5.111 Principles of Chemical Science F14, lec 2 'Discovery of electron and nucleus' |
| web3 | web | mathematics | 10.0 | 7 | 56 (0) | annotated; MIT OCW 18.01 Single Variable Calculus F07, lec 1 'Derivatives, slope, velocity, rate of change' |
| web4 | web | physics | 10.0 | 7 | 75 (10) | annotated; MIT OCW 8.01 Physics I F99, lec 1 'Powers of ten, units, dimensions, measurements'; 32 failed LLM calls (connect timeouts) -> long queue |
| web5 | web | computer science | 10.0 | 9 | 37 (3) | annotated; NPTEL Computer Networks (IIT Kharagpur), lec 1 |
| web6 | web | economics | 10.0 | 10 | 85 (0) | annotated; NPTEL History of Economic Theory, mod 1 lec 1; 6 failed LLM calls (429 / timeouts) |

## Phase 4 — final numbers (2026-10-15, all zero tokens; every number in the paper comes from these files)

Groups: the 30 recorded tests were given by **six speakers**; the `speaker A/B` labels in the meta files are not
reliable, so `tools/eval_sheets.py` now groups them as one **Recorded** group next to **Public** (web1–6); old labels in
`rating_key.json` are mapped by `group_of()`. `score` also writes raw percent agreement and a split into lectures
interpreted mostly by the LLM vs. mostly by the fallback (only test29, 52/52 fallback units).

Reproduce:
```bash
.venv/Scripts/python tools/eval_sheets.py score                                   # -> verify_results/_eval/results.json
PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/sessions_stats.py # -> paper/build/fig/sessions.json (D1),
                                                                                  #    d2_stats.json (D2 groups), fig_latency.png (D2)
PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/build_docx.py paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot.docx
powershell -File paper/build/src/render.ps1 <docx> <absolute pdf path>             # pages=6
```

| Paper number | Value | Source |
|---|---|---|
| D2 size | 36 lectures, 409.2 min, 2,992 utt., 1,619 units, 72 fallback (4.4 %), 505 slides, 2 teacher deletions | results.json `dataset.all` |
| Recorded / Public | 30, 349.2 min, 1275 (59), 453 / 6, 60.0 min, 344 (13), 52 | results.json `dataset` |
| Boundary P / R / F1 / P_k (all) | 0.78 / 0.42 / 0.49 / 0.32 (Recorded 0.81/0.54/0.59/0.29; Public 0.73/0.19/0.29/0.37) | `annotation.summary` |
| LLM lectures vs. fallback lecture | P 0.77, R 0.45 (17) / test29: R 0.04, coverage 83.1 %, unsupported 0.7 % | `llm_lectures`, `fallback_lectures` |
| Key-fact coverage | 86.6 % of 669 facts (Recorded 88.0, Public 84.0) | `coverage`, `facts` |
| Unsupported / wrong | 0.9 % / 3.7 % of 2,504 statement judgments; 41 of 79 wrong marks also marked "said" | `unsupported`, `wrong`, `wrong_said`/`wrong_n` |
| κ boundaries (agreement) | 0.72 (92.3 %); Recorded 0.81 (94 %), Public 0.56 (90 %) | `kappa_boundary`, `agreement_boundary` |
| κ supported (agreement) | 0.07 (88.8 %) — prevalence paradox, nearly all marked Y | `kappa_supported`, `agreement_supported` |
| Ratings T1–T5 (30 slides) | correctness 4.15, relevance 3.89, readability 4.17, usefulness 3.87; ICC(2,1) 0.45–0.56 | results.json `ratings` |
| Latency D2 (Table II, Fig. 6) | STT 0.68 s/utt., LLM 1.96 s/call (per unit, non-fallback, n = 1547), E2E 11.2 s median, p95 53.0 s (n = 2783); wait 7.6 s, compose 2 ms | d2_stats.json, e2e_d2.json |
| Latency per group | Recorded 0.71 / 1.92 / 10.1 (23.2); Public 0.60 / 2.23 / 17.1 (93.4) | d2_stats.json |
| Without provider outages | web4 + web6 excluded (32 / 6 failed calls: timeouts, HTTP 429): median 10.2 s, p95 23.4 s, n = 2534 | d2_stats.json `no_outage`, e2e_d2_no_outage.json |
| D1 row, baseline table, images | unchanged from the earlier paper (sessions.json, ablation.json / baseline runs, D1 logs) | |
| Tests | 553 fast, 25 slow (GPU/model), 39 browser — all passed 2026-10-15 | pytest |

Note: the LLM median is reported **per call** (1.96 s), consistent with D1's 1.35 s; the per-line value from
`paper_eval.py latency` is 1.93 s. Fig. 6 now shows D2 (D1 `e2e_latency.json` is untouched).

## Phase 5 — review revision (2026-10-15, zero tokens)

Three external reviews (`paper_review/*.txt`) were answered with real, reproducible evidence only. Output:
`paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot_v3.docx/.pdf` (exactly 6 pages; the old file was open in Word).
Backup of the pre-review sources and paper: `paper/build/backup_v1/*_before_review.*`.

`tools/paper_ablation.py` → `verify_results/_eval/ablation_d2.json`: recorded signals + LLM answers of the 18 annotated
lectures replayed through planner variants, scored like `eval_sheets.py score`. The full replay reproduces the live
result exactly (P 0.78, R 0.424, F1 0.49, P_k 0.32) — validation of the replay.

| Paper number | Value | Source |
|---|---|---|
| Table IV ablation (P / R / P_k / changes per min / shown < 10 s) | full 0.78/0.42/0.32/1.15/16; no dwell …/25; no confirmation 0.79/0.45/0.31/1.12/10; LLM labels decide 0.78/0.46/0.30/1.17/21; each concept a new slide 0.37/0.86/0.47/3.18/200 | `ablation_d2.json variants` |
| Dwell sweep | 0–20 s: P/R unchanged; 30 s 0.76/0.41; 45 s 0.67/0.32 | `sweep_dwell` |
| tau sweep | only affects confirmation; 0.5–1.01: P 0.78–0.79 (not in paper) | `sweep_tau` |
| 95 % bootstrap CIs (per lecture, 2000×, seed 2026) | P 0.68–0.88, R 0.30–0.55, coverage 84.6–88.5 %, unsupported 0.2–1.8 % | `*_ci` + bootstrap of results.json lecture rows |
| Gwet AC1 / PABAK "supported" | all 0.88 / 0.83 (p_o 0.89, n 1252); Recorded 0.89; Public 0.84 | `supported_agreement` (+ per-group run) |
| Model shares of 1,619 D2 units | gpt-oss-120b 71.6 %, qwen3.8-27b 24.0 %, fallback 4.4 % | InterpretationReady.provider (groq_main / groq_alt) |

Honest findings now in the paper: the topic-confirmation rule shows no measurable benefit on D2 (kept as safeguard);
the stability comes from the extend-not-rewrite operations + dwell; the LLM baseline is labelled a D1
(development-set) comparison. Fig. 4 (study notes) was removed (feature not evaluated; reviewers: scope), the Fig. 3
control view is the 2026-10-15 screenshot, the slide grid is 3×3 at full width.
To confirm by the authors: the speakers' consent sentence and "annotations … available on request".

## Phase 6 — second review round (2026-10-15; ChatGPT + Claude reviews of v3)
New analyses (tools in `tools/`, outputs in `verify_results/_eval/`):

| Result | Value | Source |
|---|---|---|
| Coverage guard contribution (18 annotated D2) | coverage 86.6 % with, 77.7 % without (60 of 669 facts only via a restored sentence); +9.0 pp, 95 % CI 6.4–11.7 | `tools/paper_guards.py` → `guards_d2.json` (guard log lines matched to transcript rows, ≥ 0.6 word overlap) |
| Copilot churn on D2 (18 lectures) | 91 of 4,515 shown statements changed in the next version (2.0 %): 24 extended, 7 teacher, rest composer merges / part moves | `guards_d2.json churn` + ad-hoc categorisation (session notes) |
| WER, web1 (MIT 7.016 lec 11, clip 3:00–13:00) | 7.1 % (S 18, D 46, I 25; 1,257 ref words); conservative normalisation | `tools/paper_wer.py`, captions `verify_results/_eval/captions/` (archive.org MIT item); only web1 has human captions |
| Fallback vs LLM structure (annotated D2) | test29: 13 slides, 3 layouts, 11 key-points; 17 LLM lectures: 223 slides, 12 layouts, 34 % key-points | Lecture.content layouts |
| LLM-controlled baseline on D2 (18 annotated, same 850 units) | rewritten/removed shown statements 38.2 % (1,439/3,763) vs 2.0 % (91/4,515); missing from final deck 65.8 % vs 6.2 %; P 0.72 vs 0.78 (p = 0.34), P_k 0.36 vs 0.32 (p = 0.15); slides/min 0.79 vs 1.25; per-lecture rewrite gap 39 pts (95 % CI 32–47), copilot lower in 18/18, exact sign-flip p = 7.6e-6 | `tools/baseline_llm_slides.py <test>` (499,144 Groq tokens; gpt-oss 481 / qwen 369 answers; 0 failed after retries) → `artifacts/baseline/<test>.json`; `tools/paper_baseline_d2.py` → `baseline_d2.json` |

Output: `paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot_v4.docx/.pdf` (6 pages; figures re-anchored, all full width:
Fig. 1 architecture 6.0", Fig. 2 control 6.8", Fig. 3 materials 7.0", Fig. 4 slides 6.9"). Discussion merged into
"Discussion and Conclusion"; Table V is now the D2 comparison; equations renumbered (1)–(4).
Paper changes: "never rewrite" made precise (LLM cannot rewrite/delete; composer merge, mis-hearing fix or teacher
can); contribution (2) = extend-only policy enforced by the planner; dwell row explained (delays, not cancels);
Qwen3 report cited; public lectures named; materials figure restored (cropped, "not evaluated"); planner flowchart
and latency CDF removed (small, unreadable; content in eq. (6) and Table II); D1 image-search sentence dropped.

## Phase 7 — third review round (2026-10-16; ChatGPT + Claude reviews of v4) → v5
0 tokens. Output `paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot_v5.docx/.pdf`, 6 pages.
- Wording: the LLM *cannot* rewrite shown content (planner executes only extending operations); limited changes
  (composer merges, accepted corrections) are measured. Abstract ratings now "mean ratings of 3.87–4.17".
- The 7 "teacher" changes in `guards_d2.json` were re-inspected from the event logs: 6 followed a `resolve_concern`
  (teacher accepted a correction; test10, test15), 1 followed a `notes_follow` toggle (not an edit) → reported as
  24 extended / 6 accepted corrections / 61 composer merges. The setup text now says teachers deleted two items and
  accepted concern-card corrections in two lectures.
- Table V note defines Slides/min (content slides made; Table IV counts projected-slide changes) and the rewrite /
  missing denominators; the baseline comparison is stated as whole-system (baseline also lacks guards/composer).
- qwen/qwen3.8-27b cited as "of the Qwen3 family [Yang et al.]".
- Fig. 3: full pages (notes p2, p3, assignment), only blank paper margins trimmed (user: no content crops).
- Not done (need new runs/people): append-only baseline, baseline key-fact coverage (needs annotation), gate sweep,
  per-model split, accented-speech WER, blinded baseline rating.
