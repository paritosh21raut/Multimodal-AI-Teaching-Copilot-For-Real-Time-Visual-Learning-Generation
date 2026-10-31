# test40 — M1 live (4.4 min, 23 segments, 8 slides) · verdict: **fix**

| # | line (as heard) | result | why |
|---|---|---|---|
| 1 | box on incline 30° | yes | slide, θ |
| 2 | mass 5 kg | yes | m = 5 kg |
| 3 | push up the slope 5N ("… happens") | yes | F up_slope |
| 3b | repeated: "push the box **up with the** slope with 5N. And that concludes today's session." | **no** (our bug) | the repeat without a clear way replaced the said direction → "which way not said", no f, no a |
| 4 | μ 0.3 | partly | in panel; f, a lost by 3b |
| 5 | "**Christian** always opposes …" | yes | nothing changed (STT mishear) |
| 6 | 45 degree | yes | θ = 45°, N = 34.6 |
| 7 | two blocks on the floor | yes | stack drawn |
| 8 | 2 kg / 3 kg | yes | top / bottom right |
| 9 | 50N on the bottom block | yes | F = 50 N right |
| 10 | "between the **block** is 0.4", floor frictionless | **no** (our bug) | μ = 0 kept, 0.4 dropped: "between the block" (singular) not read → no a, "friction coefficient not said" |
| 11 | pulley, two blocks | yes | |
| 12 | 2 kg / 3 kg | yes | a = 1.96, T = 23.5, 3 kg down |
| 13 | table + rope + pulley (said twice) | yes | one slide, rope over the edge pulley |
| 14–15 | 4 kg / 1 kg, μ 0.2 | yes | a = 0.392, T = 9.41, f = 7.84, slides |
| 16 | spring with a mass | yes | |
| 17 | repeat heard as "spring with a **hanging mass**." + "from it." | **no** (our bug) | no new slide, but a 2nd mass part "hanging mass" was added |
| 18 | "0.5kg … spring constant is **100Nm**. meter." | **no** (our bug) | m unattached (2 masses now); "100Nm" read as a force, not k → no x, no T |
| 19 | "Newton's law, the basics of mechanics." | partly | no slide, diagram unchanged; it went into the spring recap at the end |

## Bugs (ranked)
1. **Repeat adds a body** (17): "a spring with a hanging mass" on an open spring+mass scene adds `hanging_mass`. Fix: a body phrase whose kind already hangs from that spring/pulley = the same body (repeat), no new part.
2. **k from STT forms** (18): after "spring constant" / "stiffness", a number + `Nm` / `N m` / `N/m` / "newtons per meter|metre" is k (unit N/m), never F.
3. **μ "between the block"** (10): accept "between the block(s)", "between them" when a stack exists.
4. **Direction lost on a repeat** (3b): a new F with the same value and no direction keeps the said direction (logged).
5. Pulley panel heads both read "HANGING BLOCK" → "2 kg block" / "3 kg block" (name by the said mass, or left/right).
6. Table: hanging mass's "W = 9.8 N" label runs under the panel (clamp labels off the panel, not only tips).
7. Minor: a line after the last scene joins its recap (Newton's law on "Recap: Spring"); Whisper's "And that concludes today's session." mid-segment not cut (STT, log only).

Numbers: every number on the slides is said or computed and correct (checked against the hand answers). Latency: STT p50 488 ms, p95 2.1 s; diagram ops within 1 s of the line. Tokens: 23 understanding calls, ~1.94k prompt each (~45k); diagrams 0.

## Fix round 1 (done)
Bugs 1–6 fixed (fastpath `_head` repeat match; quantities `_KSAID`, "between the block", F way kept on a same-value
repeat; contact `_name` "2 kg block"; mech label flips off the panel). Fixtures `m1_test40_{incline,stack,spring}`
(exact transcript lines) + 3 tests; full 2017 pass; transcript replay: all values right. Bug 7 left (recap scope, STT).
Re-test: `docs/v2/tests/M1-retest.md` (7 lines).
