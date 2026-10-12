# F-011 — Quiz + test through the share link (V2 group C)

Status: done, verified (2026-10-12) — see STATE.md. User decisions: 2026-10-12 (Part 2 brief; no open questions).

## Goal
The teacher runs a **live quiz** (Kahoot-style) or a **test** with the students on the existing share link (`/view`,
Cloudflare tunnel). Questions are MCQ (4 options), written by the LLM from what was taught (bounded), previewed and
edited by the teacher. Nothing is generated or shown unless the teacher asks. Timing, scoring and state are
deterministic code; the LLM only writes questions.

## Kinds
| | Quiz | Test |
|---|---|---|
| Setup | count (default 15), seconds per question (default 15), From: This lecture / Lectures / Chapters | count (default 15), duration in minutes (default 15), From, **show answers after submit** (default on) |
| Students | one question at a time, answer once, see right / wrong after the question | all questions, navigation, change answers until Submit; auto-submit at time out |
| Projector | lobby (QR + link + count) → question + timer + answer count → correct answer + distribution + top 5 → final podium | lobby → timer + "N of M submitted" + QR → (end) "Test over" |
| /control | lobby + Start; question, timer, answers in, distribution, leaderboard; Next / Hold next / Pause / Resume / End | monitor: joined / in progress / submitted per student, time left, Pause / Resume / End |
| Score | correct: `round(1000 × (1 − 0.3 × t / T))` (1000 instant → 700 at the buzzer), wrong / none: 0 | 1 point per correct answer |
| Result | final leaderboard (rank by total; ties: more correct, then less total answer time) | score / total; the correct answers too unless turned off |
| Results table (/control, CSV) | Roll no. · Points · Score (right / asked) · Avg. time (mean answer time of the answered questions) | Roll no. · Score · Time taken (test clock from joining to submit, pauses excluded; "auto" when auto-submitted) |

## Flow (one assessment at a time)
```
draft ──open──▶ lobby ──start──▶ running ──▶ finished ──close──▶ (none)
  ▲ edit / delete / add / regenerate one      │ pause ⇄ resume (quiz: whole quiz, test: global clock)
  │ (generation: "generating" while the LLM writes)   end ──▶ finished
discard (draft / lobby) ──▶ (none)
```
- Quiz `running` steps: `question` (deadline) → `reveal` (correct + distribution + leaderboard, `REVEAL_S` = 6 s) →
  next question, or **held** when the teacher pressed *Hold next* (then *Next*). A question closes early when every
  joined student answered. After the last reveal → `finished`.
- Pause freezes the remaining time (question deadline / reveal / test clock); resume adds it back.
- **Open** puts the lecture on Pause (if live) and the join form on every `/view`; **Close** resumes it (only when
  the assessment paused it) and returns `/view` and `/display` to the slides.
- Test: one global deadline from Start; a late joiner gets what is left. At the deadline every unsubmitted student is
  submitted (`auto`). End = the same, now.

## Students (`/view`)
- Join: name + roll number. Roll numbers are normalised (trim, case-insensitive, inner spaces removed). One
  participant per roll number: the join returns a **token** kept in the page's `localStorage`; a refresh rejoins
  with roll + token (answers, score and the timer are kept). The same roll number without that token is refused
  ("already joined"); the teacher can release a roll number (another device takes it over, answers kept). Joining
  is open in lobby and running (quiz: the open question too, while its time lasts); not after finished.
- Ties: equal points share a rank (quiz tie-break: more right answers, then less time on the right answers).
- One submission per roll number; after submit (or auto-submit) the answers are locked.
- **Answer key never leaves the core before it is due:** a quiz question's correct option is sent only in its reveal;
  test answers only in a submitted student's own result (and only when *show answers* is on). Students' pages get
  the public state (no keys) on the WebSocket and their own state over HTTP with their token.

## Teacher (`/control`)
- **Quiz & Test** tab: kind, count, time, From picker (same as Materials), *show answers* (test) → **Prepare quiz /
  Prepare test**.
- Preview: every question editable (text, 4 options, correct option), delete, add (blank, teacher writes it),
  regenerate one (LLM, avoids the others). Then **Open** (lobby). **Back to setup** (draft or lobby) drops the set
  after a confirm (`assess_discard`); the setup keeps the choices it was made with.
- Lobby: participant count + names, the join link + QR, **Start**.
- Live views as in the table; **End** any time.
- Results: table (see Kinds; review 2026-10-12) + **CSV**. Saved with the lecture
  (`data/assessments/<id>.json`); the Lectures tab lists a lecture's quizzes / tests with their results + CSV.

## LLM (slice 2)
One call for the set (repair once), one call per regenerated question. Material: `content.budgeted` over the chosen
lectures' slides (+ what was said, bounded), ≤ `PROMPT_MAX` 3000 tokens; never the whole transcript. JSON
`{"questions": [{"q": "...", "options": ["a","b","c","d"], "answer": 0}]}` validated: 4 distinct non-empty options,
answer 0–3, no duplicate stems. Options are shuffled by the core (seeded), so the key position is not the LLM's.

## Architecture
- `copilot/assess/`: `model.py` (Assessment state machine; pure, every method takes `now`), `scoring.py`,
  `store.py` (JSON per assessment, atomic writes), `service.py` (AssessService: the single writer; bus commands from
  /control, student calls from the server; a ticker advances the clock; publishes `AssessState`), `generator.py`
  (slice 2).
- Commands (control only): `assess_create {kind, count, seconds|minutes, show_answers, current, lectures, chapters}`,
  `assess_edit {qid, text, options, answer}`, `assess_add {}`, `assess_delete {qid}`, `assess_regen {qid}`,
  `assess_open`, `assess_start`, `assess_pause`, `assess_resume`, `assess_hold {on}`, `assess_next`, `assess_end`,
  `assess_close`, `assess_discard`.
- `AssessState` (ephemeral): `control` (everything, keys included) to /control; `public` (no keys before due) to
  /display and /view.
- Student HTTP (slice 3): `POST /api/assess/join`, `GET /api/assess/me`, `POST /api/assess/answer`,
  `POST /api/assess/submit`. Results (teacher only): `GET /api/assess?lecture=`, `GET /api/assess/{id}`,
  `GET /api/assess/{id}/results.csv`.

## Slices
1. Spec + core (state machine, scoring, registry, rejoin, persistence, events / commands; fake-clock tests).
2. Question generation (bounded, JSON validation, regenerate one; fake LLM; 0-token dry tool).
3. `/view` student flow. 4. `/control`. 5. `/display`. 6. Runtime check (0 tokens, Edge, ≥ 3 students). 7. One small
live Groq generation.
