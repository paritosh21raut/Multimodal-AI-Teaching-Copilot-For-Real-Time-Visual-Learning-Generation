"""Real browser (installed Edge via Playwright) against the real display server (F-003).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_display_browser.py
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.presentation.spec import Item, PointsBlock, SlideSpec  # noqa: E402

pytestmark = pytest.mark.browser
ART = Path(__file__).resolve().parents[2] / "artifacts" / "app"


def points(slide_id, texts):
    return SlideSpec(id=slide_id, title="Rapid updates", layout="key_points",
                     blocks=[PointsBlock(id="p", items=[Item(id=f"i{n}", text=t) for n, t in enumerate(texts)])])


async def command(h, kind, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await h.settle()


async def test_rapid_in_place_updates_do_not_recreate_existing_nodes():
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        await h.deck.add(points("s", ["First point stays put"]))
        await h.settle()
        await wait_for_slide(page, "s")
        # Tag the live DOM nodes and count removals from now on.
        await page.evaluate("""() => {
            window.__removed = 0;
            document.querySelector('.slide').__tag = 'slide';
            document.querySelector('.point').__tag = 'first';
            new MutationObserver(ms => ms.forEach(m => m.removedNodes.forEach(n => {
                if (n.nodeType === 1 && (n.matches('.point, .slide'))) window.__removed++;
            }))).observe(document.body, { subtree: true, childList: true });
        }""")
        texts = ["First point stays put"]
        for i in range(100):
            if len(texts) < 5 and i % 20 == 0:
                texts.append(f"New point {len(texts)}")
            else:
                texts[-1] = texts[-1].split(" #")[0] + f" #{i}"
            await h.deck.update(points("s", texts))
        await h.settle()
        await page.wait_for_function("t => [...document.querySelectorAll('.point')].at(-1)?.textContent.includes(t)",
                                     arg=texts[-1].split(" ", 1)[1], timeout=5000)
        result = await page.evaluate("""() => ({
            removed: window.__removed,
            sameSlide: document.querySelector('.slide').__tag === 'slide',
            sameFirst: document.querySelector('.point').__tag === 'first',
            slides: document.querySelectorAll('.slide').length,
            items: document.querySelectorAll('.point').length,
        })""")
        assert result == {"removed": 0, "sameSlide": True, "sameFirst": True, "slides": 1, "items": len(texts)}
        assert page.errors == []


async def test_slide_change_completes_in_a_window_the_browser_does_not_paint():
    """Live test 2026-10-06: /display popped out as its own window (behind /control) or as a background tab kept the
    old slide until reloaded. Edge pauses animation frames for such windows; the slide change waited on one, and the
    next in-place update cancelled the pending step, so the new slide stayed invisible. Simulated here: animation
    frames never run."""
    no_frames = "window.requestAnimationFrame = () => 0; window.cancelAnimationFrame = () => {};"
    async with display_harness() as h, browser_page(f"{h.url}/display", init_script=no_frames) as page:
        await h.deck.add(points("a", ["alpha"]))
        await h.settle()
        await wait_for_slide(page, "a")
        await h.deck.add(points("b", ["beta"]))           # the teacher moves on (or presses → in /control)
        await h.settle()
        await asyncio.sleep(0.1)
        await h.deck.update(points("b", ["beta", "more"]))  # an in-place update right after
        await h.settle()
        await wait_for_slide(page, "b")
        await page.wait_for_function("() => document.querySelectorAll('.slide').length === 1", timeout=3000,
                                     polling=100)
        await command(h, "prev")
        await wait_for_slide(page, "a")
        await page.wait_for_function("() => getComputedStyle(document.querySelector('.slide')).opacity === '1'",
                                     timeout=3000, polling=100)
        assert page.errors == []


async def test_first_slide_is_awaited_behind_glass_without_text():
    """User 2026-10-06: before the first slide the projector must not look frozen, and no "preparing" text:
    something moves behind a glass pane. Between slides nothing is shown (the previous slide stays)."""
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        await page.wait_for_selector(".glass .blob", timeout=5000)
        moving = await page.evaluate("""() => [...document.querySelectorAll('.glass .blob')]
            .map(b => getComputedStyle(b).animationName).filter(n => n && n !== 'none').length""")
        assert moving >= 2
        assert (await page.inner_text(".viewport")).strip() == ""   # no words on the projector
        # round 5 (user 2026-10-06): anticipation, like an image being generated: light runs around a slide-shaped
        # glass card, and a slide's outline (crumb, title, lines, picture) is drawn inside it piece by piece
        drawn = await page.evaluate("""() => ({
            ring: getComputedStyle(document.querySelector('.glass .ring')).animationName,
            pieces: [...document.querySelectorAll('.glass .sk')].filter(e => getComputedStyle(e).animationName
                .includes('glass-build')).length,
            card: document.querySelector('.glass .card').getBoundingClientRect().width })""")
        assert drawn["ring"] == "glass-spin" and drawn["pieces"] >= 6 and drawn["card"] > 0
        await page.wait_for_timeout(1800)  # a few pieces drawn
        await page.screenshot(path=str(ART / "display_first_slide_glass.png"))
        await h.deck.add(points("a", ["alpha"]))
        await h.settle()
        await wait_for_slide(page, "a")
        # the glass clears over the first slide, then goes
        await page.wait_for_selector(".glass.leaving", timeout=2000)
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(ART / "display_first_slide_glass_clearing.png"))
        await page.wait_for_selector(".glass", state="detached", timeout=3000)
        await command(h, "blank")   # blank is empty, not the glass
        await page.wait_for_function("() => document.querySelectorAll('.slide').length === 0", timeout=3000)
        assert await page.query_selector(".glass") is None
        assert page.errors == []


async def test_blank_and_navigation_on_projector():
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        await h.deck.add(points("a", ["alpha"]))
        await h.settle()
        await wait_for_slide(page, "a")
        await h.deck.update(points("a", ["alpha", "changed later"]))
        await h.deck.add(points("b", ["beta"]))
        await h.settle()
        await wait_for_slide(page, "b")

        await command(h, "blank")
        await page.wait_for_function("() => document.querySelectorAll('.slide').length === 0", timeout=3000)
        await command(h, "unblank")
        await wait_for_slide(page, "b")

        await command(h, "prev")
        await wait_for_slide(page, "a")
        texts = await page.locator(".slide:not(.is-leaving) .point > span:last-child").all_inner_texts()
        assert texts == ["alpha", "changed later"]
        assert page.errors == []


async def test_display_reconnects_by_itself_after_the_server_drops():
    from copilot.display.server import DisplayServer

    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        await h.deck.add(points("a", ["alpha"]))
        await h.settle()
        await wait_for_slide(page, "a")
        port = h.server.port
        await h.server.stop()  # every socket drops
        await h.deck.update(points("a", ["alpha", "sent while disconnected"]))
        await h.settle()
        await asyncio.sleep(0.5)
        h.server = DisplayServer(h.hub, port=port)
        await h.server.start()
        # no reload: the client's own reconnect gets a full hello snapshot
        await page.wait_for_function("() => document.body.innerText.includes('sent while disconnected')", timeout=8000)
        assert page.errors == [] or all("WebSocket" in e or "ERR_CONNECTION" in e for e in page.errors)


async def test_an_open_tab_reloads_itself_when_the_client_files_changed(tmp_path):
    """Live tests 2026-10-06: a /control tab left open from an earlier run reconnected to the new app but kept the
    pre-V1a renderer (no KaTeX, no subscripts). After a reconnect the page must load the current client files."""
    import os
    import shutil

    from copilot.display.server import WEB_ROOT, DisplayServer

    web = tmp_path / "web"
    shutil.copytree(WEB_ROOT, web)
    async with display_harness() as h:
        port = h.server.port
        await h.server.stop()
        h.server = DisplayServer(h.hub, port=port, web_root=web)
        await h.server.start()
        await h.deck.add(points("a", ["alpha"]))
        await h.settle()
        async with browser_page(f"{h.url}/display") as page:
            await wait_for_slide(page, "a")
            before = await page.evaluate("() => document.querySelector('meta[name=client-version]').content")
            await h.server.stop()
            css = web / "shared" / "tokens.css"
            css.write_text(css.read_text(encoding="utf-8") + "\n/* changed */\n", encoding="utf-8")
            os.utime(css)
            h.server = DisplayServer(h.hub, port=port, web_root=web)
            await h.server.start()
            await page.wait_for_function("v => document.querySelector('meta[name=client-version]')?.content"
                                         " && document.querySelector('meta[name=client-version]').content !== v",
                                         arg=before, timeout=10000)
            await wait_for_slide(page, "a")
