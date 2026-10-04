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


async def test_freeze_blank_and_navigation_on_projector():
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        await h.deck.add(points("a", ["alpha"]))
        await h.settle()
        await wait_for_slide(page, "a")

        await command(h, "freeze")
        await h.deck.update(points("a", ["alpha", "changed while frozen"]))
        await h.deck.add(points("b", ["beta"]))
        await h.settle()
        await asyncio.sleep(0.5)
        assert await page.locator(".point").all_inner_texts() == ["1\nalpha"]  # held exactly

        await command(h, "unfreeze")
        await wait_for_slide(page, "b")  # catches up with the live slide

        await command(h, "blank")
        await page.wait_for_function("() => document.querySelectorAll('.slide').length === 0", timeout=3000)
        await command(h, "unblank")
        await wait_for_slide(page, "b")

        await command(h, "prev")
        await wait_for_slide(page, "a")
        texts = await page.locator(".slide:not(.is-leaving) .point").all_inner_texts()
        assert texts == ["1\nalpha", "2\nchanged while frozen"]
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
