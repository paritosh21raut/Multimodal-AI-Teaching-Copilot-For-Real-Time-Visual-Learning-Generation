"""Quiz + test in real Edge (F-011): students on /view (phone size) are switched to the join form when the teacher
opens a quiz, join with name + roll number (a duplicate roll number is refused), answer, rejoin after a refresh with
their answers and timer, and get their result; a test is answered with navigation, submitted, and auto-submitted at
time out. No answer key reaches a student's page before it is due (every WebSocket frame and HTTP body is checked).
The questions are written by hand (assess_add): 0 tokens."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from display_harness import display_harness  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402

pytestmark = pytest.mark.browser
OUT = ROOT / "artifacts" / "assess"
QUESTIONS = [
    ("Which gas do plants take in for photosynthesis?", ["Carbon dioxide", "Oxygen", "Nitrogen", "Helium"], 0),
    ("Where does photosynthesis happen in a leaf cell?", ["Nucleus", "Chloroplast", "Ribosome", "Cell wall"], 1),
    ("Which pigment absorbs light energy?", ["Keratin", "Melanin", "Chlorophyll", "Haemoglobin"], 2),
]


async def cmd(h, command, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=command, args=args, origin="control")))
    await h.settle()


async def prepare(h, kind, **opts):
    await cmd(h, "assess_create", kind=kind, **opts)
    for text, options, answer in QUESTIONS:
        await cmd(h, "assess_add", text=text, options=options, answer=answer)
    await cmd(h, "assess_open")


class Student:
    """A phone-size page in its own browser context (its own localStorage), recording what reaches it."""

    def __init__(self, page) -> None:
        self.page = page
        self.frames: list[str] = []
        self.errors: list[str] = []
        page.on("websocket", lambda ws: ws.on("framereceived", lambda f: self.frames.append(f if isinstance(f, str) else "")))
        page.on("pageerror", lambda e: self.errors.append(str(e)))

        async def body(resp):
            if "/api/assess/" in resp.url:
                try:
                    self.frames.append(await resp.text())
                except Exception:  # noqa: BLE001  (a navigation cancelled the body)
                    pass
        page.on("response", lambda r: asyncio.ensure_future(body(r)))

    def leaked(self, words=('"answer"', '"key"', '"distribution"', '"right"', '"points"')) -> list[str]:
        return [f[:200] for f in self.frames if any(w in f for w in words)]

    async def join(self, name, roll):
        await self.page.fill("input[name=name]", name)
        await self.page.fill("input[name=roll]", roll)
        await self.page.click("form.join-form button.as-primary")


async def students(browser, url, n, theme_dark=False):
    out = []
    for _ in range(n):
        ctx = await browser.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark" if theme_dark else "light")
        page = await ctx.new_page()
        s = Student(page)
        await page.goto(f"{url}/view")
        out.append(s)
    return out


async def test_quiz_students_join_answer_rejoin_and_see_results(tmp_path):
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(assess_dir=tmp_path / "assessments") as h:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True)
            a, b, c, d = await students(browser, h.url, 4)
            proj = await (await browser.new_context(viewport={"width": 1600, "height": 900})).new_page()
            await proj.goto(f"{h.url}/display")
            await prepare(h, "quiz", count=3, seconds=20)
            # /view switched to the join form by itself, with a banner
            for s in (a, b, c, d):
                await s.page.wait_for_selector("form.join-form")
                assert "Quiz time" in await s.page.inner_text(".banner")
            await a.page.screenshot(path=str(OUT / "student_join.png"))
            await a.join("Asha", "CS-01")
            await b.join("Ben", "CS-02")
            await c.join("Chen", "cs 03")
            await a.page.wait_for_selector(".lobby-me")
            # the slide stage is not drawn under the overlay (Edge showed a composited slide through it, real app)
            assert await a.page.eval_on_selector(".stage", "e => getComputedStyle(e).display") == "none"
            await d.join("Imposter", "CS-01")  # the same roll number from another device
            await d.page.wait_for_selector(".join-form .as-error")
            assert "already joined" in await d.page.inner_text(".join-form .as-error")
            await c.page.wait_for_selector(".lobby-me")
            await a.page.wait_for_function("document.querySelector('.lobby-me .as-pulse b').textContent === '3'")
            await a.page.screenshot(path=str(OUT / "student_lobby.png"))
            await proj.wait_for_selector(".assess-proj .lobby")
            await proj.screenshot(path=str(OUT / "projector_lobby.png"))

            await cmd(h, "assess_start")
            for s in (a, b, c):
                await s.page.wait_for_selector(".q-screen .opts button.opt")
            await a.page.screenshot(path=str(OUT / "student_question.png"))
            await proj.wait_for_selector(".assess-proj .round .opt")
            await proj.screenshot(path=str(OUT / "projector_question.png"))
            await a.page.click(".q-screen .opt.o0")               # right (Carbon dioxide)
            await a.page.wait_for_selector(".locked")
            await b.page.click(".q-screen .opt.o1")               # wrong
            await b.page.wait_for_selector(".locked")
            assert not a.leaked() and not b.leaked() and not c.leaked(), "a key reached a student before the reveal"
            # Chen refreshes before answering: rejoined, the question and the timer are still there
            await c.page.reload()
            await c.page.wait_for_selector(".q-screen .opts button.opt")
            left = int(await c.page.inner_text(".q-screen .timer b"))
            assert 5 < left <= 20
            await c.page.click(".q-screen .opt.o2")               # wrong; every student answered → reveal
            await a.page.wait_for_selector(".verdict.is-yes")
            assert "+" in await a.page.inner_text(".verdict .gain")
            await b.page.wait_for_selector(".verdict.is-no")
            assert "Carbon dioxide" in await b.page.inner_text(".verdict")
            await a.page.screenshot(path=str(OUT / "student_correct.png"))
            await b.page.screenshot(path=str(OUT / "student_wrong.png"))
            await proj.wait_for_selector(".assess-proj .round.is-reveal .side-board")
            await proj.screenshot(path=str(OUT / "projector_reveal.png"))
            # the teacher pauses: students see the veil; resume; next question; end
            await cmd(h, "assess_pause")
            await a.page.wait_for_selector(".paused-veil")
            await cmd(h, "assess_resume")
            await a.page.wait_for_selector(".paused-veil", state="detached")
            await cmd(h, "assess_next")
            await a.page.wait_for_function("document.querySelector('.q-screen .eyebrow')?.textContent.includes('2 of 3')")
            await cmd(h, "assess_end")
            await a.page.wait_for_selector(".final-me")
            assert "#1" in (await a.page.inner_text(".final-me .big-rank")).replace("\n", "")
            await a.page.screenshot(path=str(OUT / "student_final.png"))
            await proj.wait_for_selector(".assess-proj .final .podium")
            await asyncio.sleep(1.4)  # the podium rises 3rd, 2nd, then 1st
            assert await proj.locator(".podium .pod").count() == 3
            await proj.screenshot(path=str(OUT / "projector_final.png"))
            await cmd(h, "assess_close")
            await a.page.wait_for_selector(".assess-me", state="detached")
            assert await a.page.eval_on_selector(".stage", "e => getComputedStyle(e).display") != "none"
            for s in (a, b, c, d):
                assert not s.errors, s.errors
            await browser.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_projector_lobby_qr_question_reveal_and_test_progress(tmp_path, theme):
    """/display: the lobby with the join QR (sharing on), the question with its timer, the reveal, the podium; then a
    test's clock + submitted progress with the late-join QR. The projector never gets a key before the reveal."""
    from display_harness import browser_page

    from copilot.core.events import ShareChanged

    async with display_harness(assess_dir=tmp_path / "assessments", theme=theme) as h:
        await h.bus.publish(ShareChanged(state="on", url="https://quiet-river-demo.trycloudflare.com/view"))
        await prepare(h, "quiz", count=3, seconds=20)
        async with browser_page(f"{h.url}/display", 1920, 1080) as proj:
            frames: list[str] = []
            proj.on("websocket", lambda ws: ws.on("framereceived", lambda f: frames.append(f if isinstance(f, str) else "")))
            await proj.reload()
            names = ["Asha", "Ben", "Chen", "Divya", "Elif", "Farah", "Gopal"]
            tokens = [(await h.assess.join(n, str(i)))["me"]["token"] for i, n in enumerate(names)]
            await proj.wait_for_selector(".assess-proj .lobby img.qr")
            qr = await proj.request.get(f"{h.url}/api/share/qr.svg")
            assert qr.status == 200 and b"<svg" in await qr.body()
            await proj.wait_for_function("document.querySelectorAll('.names li').length === 7")
            await asyncio.sleep(0.5)
            await proj.screenshot(path=str(OUT / f"projector_lobby_qr_{theme}.png"))
            await cmd(h, "assess_start")
            await proj.wait_for_selector(".assess-proj .round .opt")
            await asyncio.sleep(0.6)
            await proj.screenshot(path=str(OUT / f"projector_question_{theme}.png"))
            q = h.assess.current.questions[0]
            assert not [f for f in frames if '"answer"' in f or '"distribution"' in f], "a key reached the projector early"
            for n, t in enumerate(tokens):
                await h.assess.answer(t, q.id, q.answer if n % 3 else (q.answer + 1) % 4)
            await proj.wait_for_selector(".assess-proj .round.is-reveal .board li")
            await asyncio.sleep(0.9)
            await proj.screenshot(path=str(OUT / f"projector_reveal_{theme}.png"))
            await cmd(h, "assess_end")
            await proj.wait_for_selector(".assess-proj .final .podium")
            await asyncio.sleep(1.4)
            await proj.screenshot(path=str(OUT / f"projector_final_{theme}.png"))
            await cmd(h, "assess_close")
            await proj.wait_for_selector(".assess-proj", state="detached")

            await prepare(h, "test", count=3, minutes=20)
            tokens = [(await h.assess.join(n, f"t{i}"))["me"]["token"] for i, n in enumerate(names[:5])]
            await cmd(h, "assess_start")
            await h.assess.submit(tokens[0])
            await h.assess.submit(tokens[1])
            await proj.wait_for_function("document.querySelector('.test-proj .submitted p')?.textContent.includes('2 of 5')")
            await asyncio.sleep(0.6)
            await proj.screenshot(path=str(OUT / f"projector_test_{theme}.png"))
            await cmd(h, "assess_pause")
            await proj.wait_for_selector(".paused-badge")
            assert not proj.errors, proj.errors


async def test_teacher_prepares_edits_runs_and_reviews_a_quiz_in_control(tmp_path):
    """/control: Write questions (a fake writer, 0 tokens) → edit / delete / regenerate / add → Open → lobby → Start →
    live (key shown to the teacher, Hold next, Next) → End → results + CSV → back to the lecture → the results again
    from the Lectures tab."""
    from display_harness import browser_page

    from tests.e2e.test_materials_browser import lecture_now
    from tests.unit.test_assess import FakeSource
    from tests.unit.test_materials import FakeRouter

    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(materials_dir=tmp_path, sessions_dir=tmp_path / "sessions", session_id="now",
                               materials_router=FakeRouter(), assess_dir=tmp_path / "assessments",
                               assess_source=FakeSource()) as h:
        await lecture_now(h)
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            control.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
            await control.click(".tabs button[aria-label='Quiz & Test']")
            await control.wait_for_selector(".assess-setup")
            assert await control.locator(".assess .made-empty").count() == 0   # no footnote under the setup
            await control.fill(".assess-setup .stepper input >> nth=0", "3")
            await control.press(".assess-setup .stepper input >> nth=0", "Tab")
            assert (await control.inner_text(".assess-setup button.prepare")).strip() == "Prepare quiz"
            await control.click(".assess-setup .make-foot button.primary")
            await control.wait_for_function("document.querySelectorAll('.q-card').length === 3")
            # Back to setup (user 2026-10-12): the set is dropped, the setup keeps its choices; then prepare 4
            await control.click(".assess-back")
            await control.wait_for_selector(".assess-setup")
            assert h.assess.current is None
            assert await control.input_value(".assess-setup .stepper input >> nth=0") == "3"
            await control.fill(".assess-setup .stepper input >> nth=0", "4")
            await control.press(".assess-setup .stepper input >> nth=0", "Tab")
            await control.screenshot(path=str(OUT / "control_setup.png"))
            await control.click(".assess-setup .make-foot button.primary")
            await control.wait_for_function("document.querySelectorAll('.q-card').length === 4")
            first = ".q-card >> nth=0"
            await control.hover(first)
            await control.click(f"{first} >> button[aria-label=Edit]")
            await control.fill(".q-editor textarea", "Which gas do plants take in?")
            for i, text in enumerate(["Carbon dioxide", "Oxygen", "Nitrogen", "Helium"]):
                await control.fill(f".q-editor .q-opt-edit.o{i} input", text)
            await control.click(".q-editor .q-opt-edit.o0 .key-pick")
            await control.click(".q-editor-foot button.primary")
            await control.wait_for_function("document.querySelector('.q-card p').textContent === 'Which gas do plants take in?'")
            assert "Carbon dioxide" in await control.inner_text(".q-card >> nth=0 >> li.is-key")
            await control.hover(".q-card >> nth=1")
            await control.click(".q-card >> nth=1 >> button[aria-label=Delete]")
            await control.wait_for_function("document.querySelectorAll('.q-card').length === 3")
            before = await control.inner_text(".q-card >> nth=1 >> p")
            await control.hover(".q-card >> nth=1")
            await control.click(".q-card >> nth=1 >> button[aria-label='Write a different question']")
            await control.wait_for_function(f"document.querySelectorAll('.q-card p')[1].textContent !== {json.dumps(before)}")
            await control.click(".add-q")
            await control.fill(".q-editor textarea", "Which pigment absorbs light?")
            for i, text in enumerate(["Keratin", "Melanin", "Chlorophyll", "Haemoglobin"]):
                await control.fill(f".q-editor .q-opt-edit.o{i} input", text)
            await control.click(".q-editor .q-opt-edit.o2 .key-pick")
            await control.click(".q-editor-foot button.primary")
            await control.wait_for_function("document.querySelectorAll('.q-card').length === 4")
            await control.screenshot(path=str(OUT / "control_preview.png"))
            assert h.hub.assess_public == {}                       # nothing reaches the students before Open

            await control.click(".make-foot.sticky button.primary")  # Open the quiz
            await control.wait_for_selector(".lobby-card .share-warn")  # sharing is off in this harness
            me = await h.assess.join("Asha", "CS-01")
            await control.wait_for_selector(".lobby-card .student-list li:has-text('Asha')")
            await control.wait_for_selector(".preview .flags .flag:text('QUIZ ON SCREEN')")
            await control.screenshot(path=str(OUT / "control_lobby.png"))
            await control.click(".lobby-card button.primary")      # Start
            await control.wait_for_selector(".assess-live .live-q .opt.is-key")
            await control.screenshot(path=str(OUT / "control_live_question.png"))
            await control.click(".live-controls button:has-text('Hold next')")
            await control.wait_for_selector(".live-controls button.on:has-text('Hold next')")
            q1 = h.assess.current.questions[0]
            await h.assess.answer(me["me"]["token"], q1.id, q1.answer)  # everyone answered → the answer shows
            await control.wait_for_selector(".assess-live .opts.revealed .opt.is-right")
            h.clock_offset += 7                                     # past the reveal: held for the teacher
            await control.wait_for_selector(".live-head .pill:text('Waiting for you')")
            await control.screenshot(path=str(OUT / "control_live_held.png"))
            await control.click(".live-controls button:text-is('Next')")
            await control.wait_for_selector(".eyebrow-c:text('Question 2 of 4')")
            await control.click(".live-controls .danger-text")      # End (confirm accepted)
            await control.wait_for_selector(".assess-live .results td:has-text('Asha')")
            heads = [t.strip() for t in await control.locator(".assess-live .results th").all_text_contents()]
            assert heads == ["#", "Name", "Roll no.", "Points", "Score", "Avg. time"], heads
            cells = [t.strip() for t in await control.locator(".assess-live .results tbody tr >> nth=0 >> td").all_inner_texts()]
            assert cells[4] == "1/2" and cells[5].endswith(" s"), cells   # 1 right of the 2 asked, its answer time
            href = await control.get_attribute(".live-head.done a.button-link", "href")
            csv = await (await control.request.get(h.url + href)).text()
            assert "Asha" in csv and "CS-01" in csv
            await control.screenshot(path=str(OUT / "control_results.png"))
            await control.click(".live-head.done button.primary")   # Back to the lecture
            await control.wait_for_selector(".assess-setup")
            assert h.assess.current is None

            await control.click(".tabs button[aria-label=Lectures]")
            await control.click(".lecture-row.now .lecture-open")
            await control.click(".past-assess .made-main", timeout=8000)
            await control.wait_for_selector(".past-assess .results td:has-text('Asha')")
            await control.screenshot(path=str(OUT / "control_past_results.png"))
            assert not control.errors, control.errors


async def test_teacher_monitors_a_test_in_control_dark(tmp_path):
    from display_harness import browser_page

    async with display_harness(assess_dir=tmp_path / "assessments", theme="dark") as h:
        await prepare(h, "test", count=3, minutes=10)
        a = await h.assess.join("Asha", "1")
        b = await h.assess.join("Ben", "2")
        await h.assess.join("Chen", "3")
        await cmd(h, "assess_start")
        qs = h.assess.current.questions
        await h.assess.answer(a["me"]["token"], qs[0].id, qs[0].answer)
        await h.assess.answer(a["me"]["token"], qs[1].id, qs[1].answer)
        await h.assess.submit(a["me"]["token"])
        await h.assess.answer(b["me"]["token"], qs[0].id, 3)
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            control.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
            await control.click(".page-theme")                    # the control page's own dark mode
            await control.click(".tabs button[aria-label='Quiz & Test']")
            await control.wait_for_selector(".student-list .chip.submitted")
            assert "2/3" in await control.inner_text(".student-list .chip.submitted")
            assert "1 of 3" in await control.inner_text(".student-list .chip.in-progress")
            assert "1 of 3 submitted" in await control.inner_text(".live-sub")
            await control.screenshot(path=str(OUT / "control_test_monitor_dark.png"))
            await control.click(".live-controls button:has-text('Pause')")
            await control.wait_for_selector(".live-controls button:has-text('Resume')")
            await control.click(".live-controls button:has-text('Resume')")
            await control.click(".live-controls .danger-text")
            await control.wait_for_selector(".assess-live .results")   # End: everyone submitted
            assert "auto" in await control.inner_text(".assess-live .results")
            heads = [t.strip() for t in await control.locator(".assess-live .results th").all_text_contents()]
            assert heads == ["#", "Name", "Roll no.", "Score", "Time taken"], heads   # no "Right" (= the score)
            asha = [t.strip() for t in await control.locator(".assess-live .results tr:has-text('Asha') td").all_inner_texts()]
            assert asha[3] == "2/3" and asha[4] == "0:00", asha             # submitted at once, before the pause
            await control.screenshot(path=str(OUT / "control_test_results_dark.png"))
            assert not control.errors, control.errors


async def test_test_navigation_submit_rejoin_and_auto_submit(tmp_path):
    from playwright.async_api import async_playwright

    async with display_harness(assess_dir=tmp_path / "assessments", theme="dark") as h:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True)
            a, b, c = await students(browser, h.url, 3)
            await prepare(h, "test", count=3, minutes=1, show_answers=True)
            for s, (name, roll) in zip((a, b, c), (("Asha", "1"), ("Ben", "2"), ("Chen", "3"))):
                await s.page.wait_for_selector("form.join-form")
                await s.join(name, roll)
                await s.page.wait_for_selector(".lobby-me")
            await cmd(h, "assess_start")
            await a.page.wait_for_selector(".paper .choice")
            await a.page.click(".choice:nth-child(1)")            # Q1 right
            await a.page.click(".paper-foot button:text('Next')")
            await a.page.click(".choice:nth-child(1)")            # Q2 wrong
            await a.page.click(".qnav button:nth-child(3)")
            await a.page.click(".choice:nth-child(3)")            # Q3 right
            await a.page.wait_for_function("document.querySelectorAll('.qnav button.is-done').length === 3")
            await a.page.screenshot(path=str(OUT / "student_test_dark.png"))
            assert not a.leaked(), "a key reached a student before submitting"
            await a.page.click(".paper-foot button.as-primary")
            await a.page.click(".confirm button.as-primary")
            await a.page.wait_for_selector(".result .big-score")
            assert (await a.page.inner_text(".result .big-score b")) == "2"
            assert "Chloroplast" in await a.page.inner_text(".review")  # the right answer it missed
            await a.page.screenshot(path=str(OUT / "student_test_result_dark.png"))
            # Ben answers one, refreshes: the answer and the timer are kept
            await b.page.wait_for_selector(".paper .choice")
            await b.page.click(".choice:nth-child(2)")
            await b.page.wait_for_function("document.querySelectorAll('.qnav button.is-done').length === 1")
            await b.page.reload()
            await b.page.wait_for_function("document.querySelectorAll('.qnav button.is-done').length === 1")
            assert "1 of 3 answered" in await b.page.inner_text(".paper-head")
            assert not b.leaked() and not c.leaked()
            # time runs out: Ben and Chen are submitted by the core
            h.clock_offset += 61
            await b.page.wait_for_selector(".result .big-score", timeout=8000)
            await c.page.wait_for_selector(".result .big-score", timeout=8000)
            assert "ran out" in (await b.page.inner_text(".result .eyebrow")).lower()  # (shown uppercase)
            assert (await c.page.inner_text(".result .big-score b")) == "0"
            # answers are locked after submit
            r = await a.page.evaluate("""async () => (await fetch('/api/assess/answer', {method: 'POST',
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: JSON.parse(
                localStorage.getItem(Object.keys(localStorage).find(k => k.startsWith('copilot-assess:')))).token,
                qid: 'x', choice: 1})})).status""")
            assert r == 409
            for s in (a, b, c):
                assert not s.errors, s.errors
            saved = json.loads(next((tmp_path / "assessments").glob("*.json")).read_text(encoding="utf-8"))
            assert {p["name"]: p["auto"] for p in saved["participants"].values()} == {"Asha": False, "Ben": True, "Chen": True}
            await browser.close()
