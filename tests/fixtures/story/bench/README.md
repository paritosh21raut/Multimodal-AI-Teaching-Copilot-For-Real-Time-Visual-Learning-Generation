# Story benchmark (P1a, ADR-0015 addendum)

24 stories written fresh for this benchmark (not in any prompt): 8 moral / folk (`moral.json`), 8 history
(`history.json`), 8 science (`science.json`); per genre 4 well known (`familiar: true`), 4 original.
Split **by story**: dev 8 · val 4 · test 12. Tuning uses dev + val only; test is recorded and scored once, at the
end of P1b (`tools/story_bench.py --split test --final`).

## Story
```
{"id", "genre", "split", "familiar", "title",
 "cast": {key: {"kind", "name", "known"?, "gender"?, "words"?}},
 "lines": [{"text", "ev": [event], "rel": [[a, rel, b(, c)]], "end": [[a, rel, b]]}]}
```
- `name`: the words that bring it into the story; it enters on the first line that says them.
- `words`: the words that name it later (default: the name minus filler words); the scorer maps the reader's
  entities to the cast by them. A new entity named only by a pronoun is a coreference break.
- The ids that must stay the same on a line = the cast keys it refers to that entered on an earlier line
  (`story_bench.same_ids`); continuity = one id per cast member used on 2+ lines.

## Event
`{"act", "by", "to"?, "obj"?, "val"?, "never"?}` — one atomic event: the semantic action (`act`), the actor, the
target / place (`to`), the thing acted with or on (`obj`), the feeling for `react`.
- `act` in `story.ops.ACTS` → an executable meaning, scored 1 / 0.5 / 0 on what is animated.
- `act` not in ACTS → UNKNOWN_ACTION (coverage 0 now; P1b adds actions by these counts).
- `never: true` → no motion should show it (decide, hear, years passed); outside coverage, scored on honest
  fallback only, like UNKNOWN_ACTION events (no guessed gesture).

`answers.json` (written by `--record`, P1b prompt, 2026-11-02; `answers_p1a.json` = the P1a-prompt recording): `{model: {story id: [{"text", "tokens", "s"}]}}`, one per line.
