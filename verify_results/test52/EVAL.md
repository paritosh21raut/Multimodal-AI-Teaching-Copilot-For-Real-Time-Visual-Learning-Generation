# test52 — ST1 re-test (fix round 1) · EVAL

| # | Line (STT) | Result | Why |
|---|---|---|---|
| 1 | story of Albert Einstein | yes | story slide, Einstein photo 0.3 s (cached) |
| 2 | STT split "In 1905," + "A young clerk in Bern …" | **yes** | fragment joined: one scene, chips 1905 · Bern, Bern photo 5.7 s |
| 3 | … at the patent office | **yes** | new scene "the patent office", photo 5.3 s |
| 4 | Years later … Berlin | **yes** | Berlin photo 7.7 s; strip labels only "years later" |
| 5 | end of the story | yes | recap: no "story begins" bullet |
| 6 | follow a drop of water | yes | new story, drop photo |
| 7 | STT "The water drop starts in the ocean" | yes | ocean scene; photo failed (network, see below) |
| 8 | sun hits it … sky | yes | sky scene; photo failed (network) |
| 9 | drop is back in the ocean | **yes** | "scene 2 shows again", no new scene |
| 10 | Ravi met Asha at the park | yes | new story, park photo, 2 figures (previous story recapped) |
| 11 | Asha said, do you like football? | yes | bubble at Asha |
| 12 | Ravi said, yes, I love it | **yes** | bubble at Ravi, Asha's dimmed; 2 figures only |
| 13 | back to the slides | yes | ended |

Must-pass 2, 3, 4, 9, 12 yes; 5 no "story begins" → **pass**.

## Unreported
- Ocean / sky photos: retried once, both failed; Groq calls hit ConnectTimeout at the same time → the network, not the code. The plain backdrop + emoji worked as the fallback.
- Water recap: LLM paraphrases ("as vapor", "completing the cycle") are words not said; no numbers. This is the old recap path (interpretation summaries), not ST1 → note for ST2 (recap from story captions).
- Ravi and Asha share the same figure (decided: no gender guess). ST2: different figure per cast member.
- 0 story LLM calls; scene ≤ 0.1 s after the line; photos ≤ 7.7 s.
