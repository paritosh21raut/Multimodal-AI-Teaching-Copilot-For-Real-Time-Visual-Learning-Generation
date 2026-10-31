# The build loop (ADR-0014) — used for M0–M5

Goal: the user types minimal words; Claude runs the plan. One card = one session (fresh context each time).

## The user's words (the whole interface)
| User says | Claude does |
|---|---|
| `next` (in a fresh session) | Phase A + B below for the card named in `docs/STATE.md` |
| `test done` (or "test is done, evaluate") | Phase C: evaluate the newest `verify_results/testN` |
| `fix` / `go` | Phase D (the fixes Claude listed) |
| `ok` / `pass` | Phase E (close the card) |

## Phase A — build (card's Build list)
1. Read `docs/STATE.md`, the card, and only the files the card lists (grep the rest).
2. Short plan in the reply (≤ 10 lines), then implement. Fixture-first, 0 tokens.
3. Tests for the touched area; full suite once; browser tests for touched pages.
4. Gate sheet (one per theme) with yes/no checks; Claude looks at it and fixes obvious misses before showing.
5. One review subagent on the diff; fix its confirmed findings.

## Phase B — hand the live test to the user
1. Write `docs/v2/tests/<card>-live.md` (≤ 2 KB): 10–15 numbered lines to speak, each with its expected picture
   and values (yes/no checks), ~6–10 min total, plus 2 "should NOT trigger" lines and 1 repeat line.
2. Print the lines in the reply too, and the command:
   `.venv/Scripts/python tools/eval_test.py run --note "<card> live" ` (Enter to start, `q` + Enter to end).
3. Update the card Result (built, unit/browser tested, live pending) + `STATE.md` (`loop: waiting for live test`).
4. Stop. Report: STATUS / IMPLEMENTED / TESTED / VERIFIED / ISSUES / NEXT ("speak the test, then type `test done`").

## Phase C — evaluate (after `test done`)
1. Newest folder: `ls -t verify_results | head -1`. Read `transcript.txt`, `slides.md`; build ONE contact sheet
   of `slides/*.png` (scratchpad, 3 columns); grep `terminal_log.txt` for `[STAGE]|[SIM]|rejected|unattached|
   CONCERN|ERROR|401|429` — never read the whole log.
2. Score every test line against its checks: yes / no / partly, with the reason (STT mishear vs our bug).
3. Also list unreported problems (wrong numbers, duplicates, recap noise, latency > 3 s, tokens).
4. Write `verify_results/<testN>/EVAL.md` (≤ 3 KB): the table, the bug list ranked, the proposed fixes.
5. Reply with the summary and a verdict: **pass** (all must-pass lines yes) or **fix** (list). Stop.

## Phase D — fix (after `fix` / `go`)
Fix the ranked list (fixture from the test's own words first, then code), tests, one quick replay of the test
transcript (`--simulate` on `transcript.txt` or the fixture replay, 0 or few tokens). If a fix is large or changes
the plan, say so and propose a new card instead. Then either a **short re-test** (only the failed lines, back to
Phase B with a 3–6-line script) or close. Max 2 fix rounds per card; after that the leftovers go to the next card.

## Phase E — close
Card Result (≤ 1 KB), `STATE.md` (≤ 3 KB, names the next card), roadmap row status, the commit command
(`git add -A && git commit -m "<type>: <msg>" && git push origin V2-Concept-Simulation`), and the line:
**"Start a new session and type `next`."**

## Context budget (stay lean)
- A session handles one card: A+B, then C+D in the same session if the context allows; if the reply count is high
  or the context is past ~60 %, write the state into the card and ask for a new session (`next` resumes at C/D).
- Never read `docs/history/`, whole large files, or the whole terminal log; one contact sheet per look.
- Live LLM: one small run per session at most (state the token estimate first); the user's live test is the run.
