# Prompt for the final paper session

Paste everything below the line into a new Claude Code session (branch `CLAUDE_rebuild`).

---

Finish the IEEE conference paper. This is phase 4 of the validation campaign in `docs/paper/VALIDATION.md`.
Read these first: `docs/STATE.md`, `docs/paper/VALIDATION.md`, `paper/build/src/body.py`, `paper/build/src/content.py`,
`paper/build/src/sessions_stats.py`, `verify_results/_eval/results.json`, the professor's list (below) and
`chatGPT_paper_review.txt`.

## Build and check
- Build: `PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/build_docx.py paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot.docx`
- Render: `powershell -File paper/build/src/render.ps1 <docx> <pdf>`. It prints the page count. Look at every page of the PDF.
- Recompute the scores (0 tokens): `.venv/Scripts/python tools/eval_sheets.py score`, which writes `verify_results/_eval/results.json`.
- Latency data: `verify_results/_eval/e2e_d2.json`, `e2e_web.json`. D1 is `paper/build/fig/e2e_latency.json`; do not overwrite it.

## Hard constraints (never break)
- Exactly 6 pages, IEEE conference format, no more and no less.
- Fig 5 keeps 9–12 slides. Keep Fig 4 (materials) if at all possible.
- No figure placed inside another section's text. Fig 1 belongs to Methodology, after Related Work.
- No "we", "our" or "us". The system is built, so write "is generated", not "can be generated".
- No future-extensions section (simulation and story mode get their own papers). No acknowledgement.
- Every Related Work reference is cited together with the reason it is used. Use "et al." for three or more authors.
  Cite borrowed formulas (P_k, Cohen's κ, ICC).
- The abstract and introduction state the problem and the novelty clearly: live slide generation from speech, a
  deterministic planner that gates the LLM, and continuity, plus the extra features (materials, quiz/test, study
  material, images).
- The quiz/test is described as implemented. Show no screenshots and no quiz results.
- Teachers and raters are named only T1–T5. Annotators are "two authors" (A and B). Never name a person.
- No `‹…›` placeholder may remain. Search body.py and content.py for `‹` before the final build.

## Title
Replace the long title with:
**"Multimodal AI Teaching Copilot: Real-Time Slide Generation from Live Lecture Speech"**
Other options if it does not fit the layout: "A Multimodal Teaching Copilot for Real-Time Visual Slides from Live
Lectures", or "Real-Time Visual Learning Generation: A Teaching Copilot that Turns Live Speech into Slides".

## Dataset wording
- The 30 recorded tests (test1–30) were given by **six speakers**. The `speaker A/B` labels in the meta files are
  wrong, so do not report per-speaker results. Merge them into one group, **"Recorded (30 lectures, 6 speakers)"**,
  next to **"Public (6 held-out MIT OCW / NPTEL lectures)"**. Change the grouping in `eval_sheets.py score` and
  `sessions_stats.py`, then recompute. Do not just average the A and B numbers.
- D2 totals (from results.json): 36 lectures, 409.2 min, 2992 utterances, 1619 units, 505 slides, 72 fallback
  units (4.4 %), 2 teacher deletions in all of D2.

## Results to fill in (real numbers only; recompute after merging the groups)
Values from the current `results.json` (all 18 annotated lectures):
- Topic boundaries (±1 utterance): precision 0.78, recall 0.42, F1 0.49, P_k 0.32. Annotator κ for boundaries is
  0.72 (substantial).
- Key-fact coverage on slides: 86.6 % (669 facts). Unsupported slide statements: 0.9 %. Wrong statements: 3.7 %
  (2504 statements).
- The κ for "supported" is about 0.07. It is low because almost every statement was marked Y (the prevalence
  paradox). Report the raw percent agreement for that label (compute it), and explain the low κ in one clause.
- Teacher ratings: 5 teachers (T1–T5), 30 slides, scale 1–5. Correctness 4.15, relevance 3.89, readability 4.17,
  usefulness 3.87. ICC(2,1) is 0.45–0.56 (moderate).
- Latency over all D2 lines (n = 2783): median 11.2 s. STT median 0.68 s, LLM call median 1.93 s, compose ≈ 0 s. The
  remaining ≈ 7.6 s is the deliberate gate, which waits until an idea is complete before a slide changes.

## How to present the results (strong and honest)
The goal is a paper that is accepted and shows the system works well. Make it convincing by choosing what to stress
and by explaining it well, never by changing or hiding data. Every number in the paper must come from
`results.json`, the latency JSONs or the ablation file, and must be reproducible.
- **Lead with the strengths:** high boundary precision (a slide changes only when the topic really changed), 87 %
  fact coverage, under 1 % unsupported statements, teacher ratings of about 4/5, and robustness: 409 minutes, 36
  lectures, six speakers plus public lectures, only 2 teacher deletions, and 4.4 % fallback units that still produced
  slides.
- **Recall:** state the low recall plainly and frame it truthfully. By design, a new concept is not a new slide, so
  the planner merges fine-grained sub-points that annotators marked as boundaries. Precision and P_k are the
  relevant measures for a projector. Report F1 as well. Do not change the ±1 tolerance to raise the numbers.
- **Latency:** stress the fast components (STT 0.68 s, LLM 1.93 s, planning ≈ 0) and explain that most of the delay
  is the intended wait for a complete idea. Report the median in the text and p95 in the table. Lectures web4 and
  web6 had external API failures (connection timeouts, HTTP 429 on the free Groq tier). It is fine to give a
  "without provider outages" median as well, but say which lectures were excluded and why, and keep the full-D2
  number in the table. Mention the fallback path as robustness: slides kept coming during the outages.
- **Baseline / ablation:** keep the existing LLM-controlled baseline comparison (Table with flips, short slides). It
  is the strongest evidence for the novelty.
- **Do not overdo it.** No "best", "perfect", "state of the art" or claims without numbers. One short limitations
  sentence (free-tier API, boundary recall, a classroom study next) makes the paper more credible to reviewers.

## Professor's 11 issues (all must be satisfied in the final version)
1. Fig 1 after Related Work, in Methodology. 2. Table I has a description of what it shows and why it matters.
3. Every reference cited with its reason. 4. No future-extensions section. 5. "et al." where needed. 6. Formulas
cited. 7. No acknowledgement. 8. Problem and novelty clear in the abstract and introduction. 9. "is generated", not
"can be generated". 10. No we/our. 11. Meaningful results showing actual performance.

## Finish
- Update `docs/paper/VALIDATION.md` (phase 4 done, final numbers) and `docs/STATE.md`.
- Report in the STATUS / IMPLEMENTED / TESTED / VERIFIED / ISSUES / NEXT format, with the final page count and a list
  of every number used and where it came from. Recommend a git checkpoint; do not commit.
