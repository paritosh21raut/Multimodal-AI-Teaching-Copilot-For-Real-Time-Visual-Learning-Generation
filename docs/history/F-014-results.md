# F-014 results (S0–S4), archived 2026-10-22 from the spec. Not read by default.

## S0 result (2026-10-17)
- **Built:** `src/copilot/simulation/` (base, registry, templates/block_on_surface + incline, values, detector,
  policy), `presentation/simulations.py` (controller in the engine), block + layout + composer column, deck
  `sim_full`, hub `sim_notice`, `GET /api/simulations`, `web/sims/` (runtime, draw, 2 scenes), slide.js layout,
  display Full stage, /control sim bar + Values + Show + pick + dock Simulation, tokens for both themes.
- **Independent physics review** (subagent): physics correct; fixed: F = μmg exactly counted as moving by a rounding
  error (a = 2.96e-16 printed), a push of unsaid direction decided printed results, tiny values printed as "5e-05".
- **Simulator run** (`incline_live.txt`, real Groq for the slides: 8 interpretations, 18,582 tokens; the
  simulation path 0): block shown at "Consider a block…", μ and 20 N followed, switch to the incline at "tilt",
  30° / μ carried, push up 20 N → at rest. Found and fixed: μ after "between the block and the floor" was missed;
  "balance the pull down the slope" set the push direction; the simulation followed onto an empty announced slide
  'What happens' — V1's heading rule took "let's see what happens" as a heading (fixed in `understanding/cues.py`).
- Open: "Now let us tilt the surface." alone switches to the incline (a setup line; by design, but early); the
  `What happens` slide shows how V1 cue fixes can come from V2 runs.

## S1 result (2026-10-17)
- **Simulation mode** (FIX 1): own slide, no new slides, collect, end cue / Back to slides / remove / topic / 180 s,
  deterministic recap (none when nothing is worth keeping), `SimulationModeChanged`, Deck `sim_mode`, /control
  "Simulation running". Browser round trip (show → teach → Back to slides → recap) in both themes.
- **Values** (FIX 2, FIX 3): unit first, bare number → last slot, push synonyms, relative phrases, μ variants; corpus
  97 lines + held-out 32 + per-template value tables (unit). The 2026-10-17 sessions replayed (`v2_eval sessions`).
- **Templates** pendulum, projectile, DC circuit, wave, orbit, unit circle: Python solver vs hand values, detector
  positives and traps, JS scene, browser row (both themes; a spoken change updates the stage), screenshots in
  `artifacts/sims` looked at, and an **independent review subagent per template**. Fixed from the reviews:
  pendulum amplitude ≤ 90° (the AGM period is wrong above); projectile one arrow scale (u, components, v), θ = 0 at
  h = 0 prints no flight, straight up R = 0; circuit SI prefixes (no "1e+06 Ω"), a slow branch still moves, P_cell
  named, CPU registers / brain / springs / capacitors guarded; wave periods in ms / µs, "high" names the amplitude,
  sound / light / standing / square waves guarded (this picture is a transverse string wave), λ bracket rides a crest,
  an unsaid amplitude says "height not to scale"; orbit "150 million km", centre-to-centre distances are the radius,
  the central body is the one named first ("orbiting the Moon, which orbits the Earth"), ellipses / comets guarded, a
  surface orbit allowed; unit circle refuses negative and π angles, angles past 360° drawn within the turn, true minus
  signs, cos x not this picture.
- **Choices made:** a switch carries said values only within a family (block ↔ incline; a pendulum's mass never
  reaches the incline); `restart_on` restarts the motion when the pendulum's length or the projectile's launch
  changes; "mentioned" stand-ins (a cliff, "at an angle") are drawn but never printed; the circuit / orbit need the
  arrangement / body said before any computed value; the dock's Simulation button becomes Back to slides while one
  runs (the dock had no room for both).
- **Open (closed in S2 except the last two):** "the period is 0.2 s" does not set f (no inverse slots); "crest to trough is 3 m" is read as λ = 3 m;
  "the string is 3 m long" is read as λ; the orbit's "at 384000 km" without "from" is the altitude; longitudinal waves,
  ellipses and cosine curves need templates of their own; the replay has only 3 cue moments (the recorded lectures
  rarely say "consider a …" with a template): the cue path is tested mostly by unit positives.

## S2 result (2026-10-18)
- **Part A.** (1) The dock's Simulation list was not empty: at 1536 px the dock is compact and
  `.dock.compact .group button:not(.icon) span {display:none}` hid the rows' text (the picker sits in the dock group;
  the Equation picker had the same bug); fixed + a browser test at the compact width. (2) Values popover names use
  the theme's text tokens (light-mode contrast). (3) S0's Simulation button pushed the dock past 1536 px into icons
  only; the dock is tighter: icon + name as before S1, icons only while My Notes is open, Simulation / Back to slides.
  (4) Push and pull (below). (5) Stage labels: one deterministic layout (`web/sims/layout.js`): each label tries its
  home, then fixed offsets, avoiding other labels, arrows and strokes (surfaces, strings, wires, the wave); off-stage
  homes are clamped back; the readout card goes to the first free corner. `test_sim_labels_browser.py` measures every
  label box in all 8 templates and both themes.
- **Forces.** `applied_n` = push (arrow onto the block at its angle), `pull_n` = pull (tail on the block, pointing
  away at its angle); both can act. Direction per force: forward / back on the floor, up / down on the incline;
  "with / against the motion" is read relative to the motion said in the line (an unsaid direction = forward / up the
  slope). Friction is printed, "(kinetic)" or "(static)". Each force gets its own angle ("pushed at 30 degrees and
  pulled at 20"). A lifted block prints a note only when N is known.
- **Graphs.** `Solution.series` (<= 2 panels, <= 3 lines, <= 400 points each; Python ticks): block / incline s-t and
  v-t over the run, pendulum theta-t (RK4, two periods), projectile y-t and v_y-t, wave y-t at one particle (two
  periods), circuit V-I per resistor and R_eq with the working point marked (no clock). The client draws each time
  line up to the scene's clock time (`graphTime`) with a dashed cursor; unknown inputs -> the curve's shape only, no
  numbers. Off by default; Show > Graph or "graph / plot" in a line. Orbit and unit circle have no series (the unit
  circle already draws sin). New readout: projectile `v_land` "Speed on landing".
- **Values said in another form** (`Template.reads`): wave "the (time) period is 0.2 s" -> f = 5 Hz, crest to trough
  -> lambda = 2d, crest to trough height -> A = d/2, "a string 3 m long" sets nothing; orbit "the Moon orbits the
  Earth at 384000 km" -> radius (altitude only with "above"). A changed value has source `computed`, counts as known,
  and prints marked computed.
- **Closed-list `sim` hint** (interpretation field, `prompt.SIM_RULE`): A/B on gpt-oss-120b (`prompt_ab.py --sim`,
  3 positive + 2 negative units, 16,027 tokens): 5/5 valid, no item change from the rule, +55 prompt tokens per
  call; sim right in 2/3 positives (missed the projectile), 0/2 false on negatives. **Not live:** too few units, and
  nothing consumes it yet; the field parses to the closed list only.
- **Eval:** `v2_eval values/sessions/detect` before / after (`verify_results/_eval/v2_s2_before.txt`, `_after.txt`):
  values 82 P/R 1.00 (now incl. pull_n, pull_angle_deg), detect show precision 1.00 (3/3), recall 1.00, 0 shows or
  suggestions on the negative lectures, topic chips 3/4. Detector: the verbs "pulled / pulling / pull it", "drag", "rope" reveal the pull, not the push; "a larger pull down the slope" (gravity) and "pulleys" do not (found in the simulator run).
- **Runtime:** simulated lecture incline_mode.txt (real Groq, 11 interpretations, 0 fallbacks): cue -> simulation mode, floor -> incline switch, 30 -> 40 -> 45 degrees, double the mass, end cue -> 2 recap slides, then Pulleys.
- **Review subagent** (graphs + forces + values): 3 confirmed parser bugs fixed (a pull's angle taken by the push via
  the word "angle"; a second force's angle dropped; incline with / against fixed to one side). Open (plausible):
  "tension 40 N" not read as the pull; an exact N = 0 prints "0 N (kinetic)"; "towards the left" not a direction;
  "coefficient of friction 0.2" without "is / of"; forces are not carried on a floor / incline switch.

## S3 result (2026-10-19)
- **Process model** (`simulation/steps.py`, `SimBase.steps / step / step_by / cycle / named`): each step is drawn and
  numbered from the start, its name printed only once said (or gone to with Next / Prev: source teacher); none is
  highlighted until the first is said; a line naming several steps names them all, the first is current; optional
  steps (transpiration, runoff, Bohr absorb / emit) are drawn only once said; strong words beat `weak` words ("rain",
  "water vapour rises", "H⁺ ions" alone); after 20 s with no step word the steps cycle every 4 s (never naming);
  parts' labels print once named. `/control`: Prev / Next and "k / n" on the sim bar (events `sim_next`, `sim_prev`).
- **Templates (5, all built):** water cycle; heart (HR from speech, "a beat lasts 0.8 s" → 75 bpm computed; CO only
  with HR and stroke volume said; valves open / shut with the phases); photosynthesis (word equation term by term,
  respiration only if said); Bohr atom (Z ≤ 20 from a name or atomic number, shells 2, 8, 8, 2, config + valence;
  energies / λ for hydrogen only; ions, orbitals, Z > 20 → notices; a jump into a full inner shell is not drawn, a
  note says why); acid–base neutralisation (strong acids × strong bases at 25 °C: exact pH, V(eq), salt name and
  formula; H₂SO₄ and weak ones drawn, no pH, a notice; pH–V graph only with c(acid), V(acid), c(base) said; each
  amount tied to the chemical said nearest it; a lone volume is the base added; "5 mL more" → a notice to say the
  total). Template hooks: `parse` (slot `"!"` = notice → `SimulationNotice`, `"~"` = a number read as nothing),
  `listens` (a line with "sodium" and no number still reaches the open simulation).
- **Detection:** a process shows on a cue in the same line; a setup only in the look-back lines or an announced topic
  ("let us learn neutralization reaction", the user's live test) gives a Suggest chip. `let's` also as "lets".
- **S2 leftovers fixed:** "tension 40 N" = the pull; an exact N = 0 prints no "(kinetic)"; "towards the left / right"
  is a direction; "coefficient of friction 0.2" without is / of; forces carried on a floor ⇄ incline switch (the
  `v2_eval sessions` rows that changed are exactly these carries).
- **Browser flake (S2):** cause = the test read the server state right after a click while the command was still in
  flight (`settle` drained only the bus). Reproduced 4/20 with a 200 ms delay injected into
  `DisplayHub.handle_client_message`; fixed with `Harness.until(predicate)` (26/26 with the delay). Other e2e files
  with click-then-`settle` were not audited.
- **Also fixed:** `/api/simulations` returned at most 10 templates (13 now): the picker hid three (caught by the S2
  dock test). `test_orbit_traps` changed by requirement: a Bohr-model line is now a `bohr_atom` cue, so the test
  asserts "not an orbit" instead of "nothing".
- **Reviews:** two independent subagents. (1) Water cycle / heart / photosynthesis: findings 1–14, 17 fixed with tests.
  (2) Bohr / neutralisation: amounts given to the other chemical's slot, chemical chosen by dict order ("acetic acid
  instead of hydrochloric acid"), "neutralise" in biology / physics opening the sim, missing "is neutralised",
  "shells go from 2 to 3" read as a jump, a jump into a full shell, "lead us / iron rod / calcium carbonate" as atoms,
  water dilution / spelt formulas ("H C L") / "5 mL more", concentrations of nothing named, pH to 3 s.f. (now 2
  decimals), flask picture rounding to "no H⁺" short of equivalence, "hydrogen iodide", bare "water is H2O": all fixed
  with tests.
- **Open:** numbers shift when an optional step is said later (review 15); the heart's valves skip the
  isovolumetric phases (16); "the human heart" setup is fairly broad (4); ions by symbol ("Na plus ion") give no
  notice; "the light falls back" can name the Bohr emit step; with every amount said and no base volume, the graph
  marks V = 0 as now; the detector's force reveal words ("pushes the blood") reach process lines (ignored: the heart
  has no such element).
- **Eval** (`verify_results/_eval/v2_s3_before.txt` → `_after.txt`): values 97 lines P/R unchanged (1.00); detect
  54 → 59 lectures, show precision 1.00 (3/3 → 8/8), recall 1.00, 0 shows / chips on the negative lectures, suggest
  moments 3/4 → 9/10 (the test21 orbit miss predates S3); no recorded biology / chemistry lecture shows; test28 and
  the V1 neutralization live lecture give a chip only.
- **Runtime:** simulated heart_live.txt with real Groq (session 20261019-105825-2333): 10 interpretations, 0 fallbacks,
  topic chip → spoken cue → simulation mode, HR 72 read, steps 1 → 6 by speech in order with parts named, end cue →
  recap slide; 23,109 tokens (prompt + completion, app usage buckets).

## S4 result (2026-10-20): hard topics
- **Templates (8 new, 21 total; 0 LLM tokens on the simulation path):**
  - `rlc_transient`: series RLC switched on to a DC source; ζ, f₀, the capacitor voltage / current curves, the
    response slowed to ~4 s on stage with a "slowed: 4 s here = 10 ms real" note; `rlc_ac`: X_L, X_C, Z, I, phase
    ("V lags I" / "leads"), f₀, phasors at 0.25 rev/s (slowed, noted). R / L / C carry between the two (family);
    parallel RLC → notice.
  - `pn_junction`: abrupt Si at 300 K (Ge as a said choice), V_bi and W only with both dopings said, bias forward /
    reverse; drift / diffusion particles in SVG (Canvas was allowed, not needed); I–V numbers only with I_s said;
    breakdown / Zener / LED → notices.
  - `routing`: links said as letter pairs + cost (≤ 8 nodes / 14 links), Dijkstra only (distance vector /
    Bellman-Ford → notice); the S3 step model with steps from the values (`step_defs`, one visit per node + the path),
    **ordered**: speech moves at most one step past the furthest reached, a negated or asked line ("should we visit
    D?") moves nothing, no auto-cycle; the path and cost print only at the path step; the links are also a Values text
    field (checked and rewritten by the server; a refused entry gets an outline).
  - `tcp`: handshake, sliding window W, N segments, a named lost segment, timeout + cumulative ACKs; fast retransmit
    only if said; TCP / Go-Back-N / Selective Repeat as a choice; congestion control, flow control, FIN, a lost ACK,
    two losses → notices. Python schedules every event (`Solution.events`, `SimEvent`); the counts printed (sent,
    again, time in RTT) come with the note "assumed: a segment every 0.25 RTT, timeout 1.5 RTT".
  - `refraction`: Snell at a flat boundary, media by name (air / vacuum = 1 standard; water, glass, … drawn with a
    textbook index, printed only when said), an index tied to its medium (`n1_of` / `n2_of`: "now from glass into air"
    moves it), θ₂, critical angle, total internal reflection, v₂ / v₁; prisms / lenses / fibres / apparent depth →
    notices.
  - `thin_lens`: the Cartesian (NCERT) sign convention (decision 7): u printed negative, f and v signed ("+15 cm,
    other side (real)"), m signed with its wording; image height and power (D) when said; three principal rays,
    virtual images by dashed extensions, a tall image draws a shorter object so the rays still meet at it; v, m, h′
    only once the lens kind is said (convex is only drawn); "f = −20 cm" / "minus 20 cm" = concave; mirrors, the lens
    maker's formula, combinations → notices.
  - `gas_piston`: P V = n R T (kPa · L = J), the fourth from any three (computed); a change with the held quantity
    said (Boyle / Charles / Gay-Lussac, "rigid container") computes the third (`"="` parse words → computed); a change
    with nothing held, the held one changing, a result outside the drawn range, two changes that would change n →
    held back with a notice; "increased by 100 K" is a change; four said that do not fit → notice; adiabatic / real
    gas / mixtures → notices; molecules at √T, piston height on a log scale.
- **Dropped:** geometry transforms (last in the order; "drop from the end"). Not started.
- **Still frame:** each template names its still moment (`drive["still_t"]`); `stillSpec()` marks simulation blocks
  `still`: the PPTX export page and the past-lecture viewer render that moment with no clock (`data-state="still"`).
  No PNG is stored. Browser tests: export (tcp, rlc_transient) and the archive viewer (tcp).
- **S3 leftovers:** optional steps numbered after their main step ("1b", mains never renumber); no pH "now" mark
  without a base volume said, "pH of the acid" when it is 0; "Na plus" / "Cl minus" / "Mg 2+" → neutral-atom notice;
  the Bohr emit step needs "electron(s)" / "it" (not "the light falls back").
- **e2e audit:** the click-then-`settle` pattern (S3's flake) replaced by `Harness.until` in
  `test_control_browser.py`, `test_control_features_browser.py` (3), `test_reference_browser.py` (2),
  `test_review_fixes_browser.py`, `test_s2_control_browser.py` (2).
- **Reviews (3 subagents):** (a) RLC + p-n, (b) routing + TCP (16 findings), (c) refraction + lens + gas (14
  findings). Fixed with tests: all of (b) but #16; of (c) #1–#12 and most of #13–#14 (gas "by", law results out of
  range, two changes with no hold, the derived fourth counted as known, an overdetermined state, lens kind gating,
  "u =", Cartesian signs, screen / shift / "away", "image of the object", glass + water indices, "with respect to",
  "equals", bare n, "second medium", angle-of-attack / water-wave guards, "from water to air", tall images, images
  practically at infinity, "same size" at the printed value, derived gas values out of range, "Speed ratio").
- **Open:** (a) "10K resistor", "10 mhz" / "kilo hertz" / "2 m H", "10 V peak" read nothing; `wave.js` formats one
  number in JS (S1). (b) #16: TCP ACK labels 17.5 px apart at 17 px font for some W / N. (c) lens and refraction
  tweens (an image passing real → virtual slides through the lens for 0.4 s; θ₂ jumps); "from a denser to a rarer
  medium" (no media named) reads nothing; n₁ = 1 for an unnamed first medium rests on the default air (documented).
- **Eval** (`verify_results/_eval/v2_s4_before.txt` → `_after.txt`): detect 59 → 66 lectures, show precision 1.00
  (8/8 → 16/16), recall 1.00, 0 shows / chips on the negative lectures, suggest moments 9/10 unchanged; values 82
  lines P/R 1.00 unchanged.
- **Runtime:** simulated `rlc_live.txt` with real Groq (session 20261020-022538-3396): 11 interpretations, 0
  fallbacks; cue → `rlc_transient` with V, R, L, C read; second cue → `rlc_ac` (V, f, R, L, C) → end cue → recap
  slide. **It found two defects, both fixed after the run:** (1) "In a parallel RLC circuit … we will not do that
  today" was an `rlc_ac` setup and switched the open step response to the AC simulation (now guarded in both RLC
  templates; the notice still comes through `listens`); the fixture test missed it because a wrong switch and the later
  real AC show give the same template sequence, so it now asserts the template at that line. (2) "Let's look at the
  graph of the capacitor voltage" was a V1 announced topic and ended simulation mode; an announced title that is the
  open simulation's graph or its setup is no longer a new topic (`SimulationController.about_open`). Both fixes are
  unit-tested and fixture-tested only; not re-run live (budget).
- **Also fixed (V1, F-013 S3b):** the KCL / KVL aliases of the equation library held backspace bytes instead of `\b`
  (a heredoc slip), so "KCL" never named Kirchhoff's law; test added. Prompt tokens 11 × 1,975 avg ≈ 21.7k (+
  completions, est. ~24k; the usage ledger kept no per-call history for the hour).
- **Tests:** fast 1547 pass (`test_sim_hard.py` 234, S3 leftovers in `test_sim_processes.py`); browser 122 pass
  (full suite, incl. `test_sim_hard_browser.py` 20: 8 templates × 2 themes, routing Next + links field, export and
  archive still frames), then the 4 simulation browser files 66 pass after the live-run fixes.
