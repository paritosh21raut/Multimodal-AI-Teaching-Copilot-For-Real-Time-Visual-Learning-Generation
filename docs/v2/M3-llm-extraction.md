# M3 — LLM scene extraction (Groq, bounded) · F-019 §6 · loop: `docs/v2/LOOP.md`

_Read: this card, `diagram/{graph,ops,validate}.py`, `stage/director_llm.py` (the pattern), `presentation/stage.py`
(`_diagram_line`, `_drain`). Grep only: `diagram/fastpath.py`, `diagram/quantities.py`, `llm/router.py`._

## Why (probe of free wordings on the fast path, 2026-11-01)
"Imagine block A on block B on the floor": B not on the floor, and "a 50 newton force pulls block B" went on A
(the article "A"). "a 4 kg block … to a 1 kg mass": both values on the block. "It has a mass of 10 kg": a new
mass part. "The masses are 2 kg and 3 kg", "mu equal to 0.1", "half a kilogram": dropped. Free wording needs the LLM;
wrong attachments must be fixed in the fast path (they never trigger a call).

## Build
1. **Fast-path fixes** (0 tokens): lettered blocks (a label word between two nouns, a one-letter label only after its
   noun and in capitals), "a 4 kg block" = that block's mass, "a mass of 10 kg" on an open body = its mass,
   "half a kilogram" read.
2. **`diagram/extract.py`** — `Extractor(router).delta(g, before, line, draft)`: PREFIX (cached, never changed:
   ops of `diagram-spec.md` §1 + `qty`, closed kinds / rels / syms / dirs, 6 short examples), then the scene table
   (≤ 20 rows), the last 2 lines, the line, the draft. The answer = the line's **complete** ops (JSONL). ≤ 1.2k
   tokens per call (`EST_PROMPT` + `MAX_TOKENS` checked in a test). `ReplayExtractor(answers)` for tests (0 tokens).
3. **`needs_llm(text, draft, g)`**: a number said in the line that no op quotes, a value unattached, an unknown
   noun, or a diagram cue with no part. Else no call (most lines: 0 tokens).
4. **Landing**: the fast draft is drawn at once; the LLM answer is validated (unchanged validator: quotes, labels,
   ids) against the graph without that line's fast ops; ≥ 1 accepted op → the line's fast events are **superseded**
   (fold skips them; the log keeps them). Late answer for a closed scene / undone line → dropped. Logged
   `[SIM] llm <line>: n ops, refused, tokens, s`.
5. **Keys**: a 0-token ping per key at start (`GET /models`); a 401 → the key is dead for the session (logged).
6. **Paraphrase set** `tests/fixtures/diagram/m3_paraphrase.json` (30 lines, M0–M2 scenes in new words) → the same
   scene (parts kinds, rels, qty) as the fast-path wording; answers recorded once live (`tools/record_m3.py`) into
   `m3_llm_answers.json`; CI replays them (0 tokens).

### Not in M3 (to M4)
Recap line after the last scene, rope systems beyond Atwood / table, inside/outside chip, closed-diagram label,
stack scene view.

## Tests
needs_llm cases; landing supersedes / keeps the draft on refusal / drops late; prompt budget; the replay
≥ 90 % same scene; a refused invented number (validator) stays refused from the LLM.

## Gate (stop)
Paraphrase replay ≥ 90 %; live test with free wording (12 lines); tokens reported.

## Result
**Verified live** (test45–47, 2026-11-01; 3 rounds). `diagram/extract.py` (needs_llm, clean, all-or-nothing landing,
late answers keep later lines' parts), DiagramLog supersede + speech-order Undo, 0-token key ping (401 only),
fast-path fixes (lettered blocks, "a 4 kg block", "has a mass of", "no friction", "stack", μ wordings, "between A
and B", rope ≠ box). Live: 6 LLM calls, 0.7–1.9 s, 1.06–1.28k tokens each (7,015 total), 0 refused; a garbled line
("table dock … one-hand gig") still landed right. Fix rounds: a repeat cue with an implied support / without its
cue word drew more masses; recap picture talk. Paraphrase replay 30/30; 21 M3 tests; full 2069 pass.
To M4: Atwood W arrow off the slide; recap restating the cue; "a 4 kg block pulls a 1 kg mass"; switch loses LLM
fixes; quote-near-noun check; "half a kilogram".
