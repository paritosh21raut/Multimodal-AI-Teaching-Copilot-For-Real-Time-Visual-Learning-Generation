# Commands

Read only when you need a command. Lean test output: add `-q -x --no-header | tail -20`.

```bash
.venv/Scripts/python -m pip install -e ".[dev]"     # install
.venv/Scripts/python -m pip install -e ".[dev,audio,display,understanding,images]"   # full stack
.venv/Scripts/python tools/screenshot_lessons.py light human_body solar   # scripted lessons + real image search (0 LLM tokens)
.venv/Scripts/python tools/prompt_ab.py --dry <session>[:i,j]   # rebuild recorded prompts (0 tokens); without --dry: real A/B
.venv/Scripts/python tools/replay_interpretations.py <session> light --images   # recorded LLM answers + real image search (0 tokens)
.venv/Scripts/python tools/materials_check.py <session>   # lecture-material prompts from a recorded lecture (0 tokens); --live: real Groq + files
.venv/Scripts/python tools/quiz_check.py <session> [--count 15]   # quiz/test prompt from a recorded lecture (0 tokens); --live: one real set
.venv/Scripts/python tools/paper_eval.py latency <session...>   # paper: end-to-end latency from live logs (0 tokens)
.venv/Scripts/python tools/baseline_llm_slides.py <session> [--metrics]   # paper: LLM-controlled baseline (~700 tok/unit); --metrics 0 tokens
.venv/Scripts/python tools/eval_test.py run --note "..." [-- <copilot args>]   # paper validation test -> verify_results/testN; see docs/paper/VALIDATION.md
.venv/Scripts/python tools/eval_sheets.py sheets|score   # paper: annotation workbooks + T1-T3 rating form / scores -> verify_results/_eval
PYTHONPATH=paper/build/lib .venv/Scripts/python paper/build/src/build_docx.py <out.docx>   # paper; render.ps1 <docx> <pdf> prints pages
.venv/Scripts/python tools/v1_eval.py [--out f.json] [--compare verify_results/_eval/v1_baseline.json]   # F-013 metrics from event logs (0 tokens)
.venv/Scripts/python tools/v1_eval.py --replay | --gate   # F-013: engine replay (cues off/on) / gate replay (call floors), 0 tokens
.venv/Scripts/python tools/v1_eval.py --structure [names] [--out f.json]   # F-013 S2: boundaries vs annotators, part rate, child slides (0 tokens)
.venv/Scripts/python tools/v1_eval.py --s3 [names] [--list verbatim,garbage,dup,def,table,formula] [--out f.json]   # F-013 S3: representation (0 tokens)
.venv/Scripts/python tools/screenshot_s3.py [groups facts members definition formula trig compare3 tiles named_eq maxwell motion cards]   # S3 layouts + mistake cards, both themes -> artifacts/display
.venv/Scripts/python tools/prompt_ab.py --compare <session>[:i,j]   # F-013 S3b: N-way comparison rule A/B (real Groq; --dry 0 tokens)
.venv/Scripts/python tools/prompt_ab.py --said [--both|--old] <session>[:i,j]   # F-013 S3c: "never state a fact not said" A/B (real Groq)
.venv/Scripts/python tools/figure_check.py <notes.pdf ...> --ask "STM32 block diagram"   # F-013 S4: asked figure end to end (own files, web; 0 tokens) -> artifacts/figures
.venv/Scripts/python tools/make_figure_fixture.py   # F-013 S4: tests/fixtures/notes/drawn_figures.pdf (vector figures + table + note)
.venv/Scripts/python tools/screenshot_structure.py   # S2: nested Lecture Structure + child crumb, both themes -> artifacts/display
.venv/Scripts/python tools/screenshot_cues.py      # announced slide / heard list / interpreted, both themes -> artifacts/display
.venv/Scripts/python tools/v2_eval.py values|sessions|detect [names] [--list]   # F-014: values corpus P/R, 2026-10-17 sessions, detector replay vs annotations (0 tokens)
.venv/Scripts/python tools/screenshot_sims.py [light dark] [scene names]   # F-014 scenes (13 templates incl. S3 processes), sim mode + recap -> artifacts/sims (LOOK at them)
.venv/Scripts/python -m pytest                      # fast tests
.venv/Scripts/python -m pytest -m slow              # + GPU/model tests
.venv/Scripts/python -m pytest -m browser           # real Edge via Playwright (display)
.venv/Scripts/python -m pytest -m live_llm tests/e2e/test_understanding_live.py -s   # real Groq (~1 min, uses free quota)
.venv/Scripts/python tools/screenshot_display.py    # all layouts, both themes -> artifacts/display (LOOK at them)
.venv/Scripts/python tools/screenshot_app.py        # run app, screenshot /control + /display -> artifacts/app
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --demo-slides --open
.venv/Scripts/python -m copilot.audio.mic_check     # list mics, record, transcribe
.venv/Scripts/python -m copilot --audio-file tests/fixtures/audio/photosynthesis_tts.wav
.venv/Scripts/python -m copilot                     # run app ([QUOTA] → ready → Enter → live; opens /control + /display, --no-open)
.venv/Scripts/python -m copilot --mode high          # this run in high performance (default: the /control Speed switch, kept in data/preferences.json)
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt
.venv/Scripts/python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --no-wait --speed 1   # M3 runtime check (real LLM)
```

