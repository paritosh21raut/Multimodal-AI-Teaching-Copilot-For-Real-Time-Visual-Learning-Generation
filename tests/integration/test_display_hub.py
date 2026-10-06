"""DisplayHub + real server over WebSockets (F-003)."""
import asyncio
import json
import socket

import httpx
import pytest
import websockets

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived
from copilot.display.hub import DisplayHub
from copilot.display.server import DisplayServer
from copilot.presentation.deck import Deck
from copilot.presentation.spec import Item, PointsBlock, SlideSpec


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def stack():
    bus = EventBus()
    deck = Deck(bus)
    deck.attach()
    hub = DisplayHub(bus, theme="dark")
    hub.attach()
    server = DisplayServer(hub, port=free_port())
    await server.start()
    yield bus, deck, hub, server
    await server.stop()
    await bus.close()


def spec(i, *texts):
    return SlideSpec(id=i, title=i, blocks=[PointsBlock(id="p", items=[Item(id=f"{i}{n}", text=t) for n, t in enumerate(texts)])])


async def recv_until(ws, pred, timeout=3.0):
    async def loop():
        while True:
            msg = json.loads(await ws.recv())
            if pred(msg):
                return msg
    return await asyncio.wait_for(loop(), timeout)


async def test_hello_patch_fanout_and_reconnect(stack):
    bus, deck, hub, server = stack
    url = f"ws://127.0.0.1:{server.port}/ws"
    async with websockets.connect(url + "?role=display") as d1, websockets.connect(url + "?role=control") as c1:
        for ws in (d1, c1):
            hello = await recv_until(ws, lambda m: m["type"] == "hello")
            assert hello["theme"] == "dark" and hello["slides"] == {}
        await deck.add(spec("a", "one"))
        await deck.update(spec("a", "one", "two"))
        await bus.drain()
        for ws in (d1, c1):
            m = await recv_until(ws, lambda m: m["type"] == "patch" and m["version"] == 2)
            assert [i["text"] for i in m["spec"]["blocks"][0]["items"]] == ["one", "two"]
    # a new client gets the full current deck in its hello
    async with websockets.connect(url + "?role=display") as d2:
        hello = await recv_until(d2, lambda m: m["type"] == "hello")
        assert hello["slides"]["a"]["version"] == 2
        assert hello["deck"]["live_id"] == "a"


async def test_control_commands_reach_bus_and_display_cannot_command(stack):
    bus, deck, hub, server = stack
    got = []

    async def rec(e):
        got.append(e.command)

    bus.subscribe("rec", rec, [CommandReceived])
    url = f"ws://127.0.0.1:{server.port}/ws"
    async with websockets.connect(url + "?role=control") as c, websockets.connect(url + "?role=display") as d:
        await c.send(json.dumps({"type": "command", "kind": "blank"}))
        await recv_until(d, lambda m: m["type"] == "deck" and m["deck"]["blank"])  # display sees the result
        await c.send(json.dumps({"type": "command", "kind": "explode"}))
        err = await recv_until(c, lambda m: m["type"] == "error")
        assert "invalid command" in err["error"]
        await d.send(json.dumps({"type": "command", "kind": "next"}))
        err = await recv_until(d, lambda m: m["type"] == "error")
        assert "only the control view" in err["error"]
    await bus.drain()
    assert [(c.kind, c.origin) for c in got] == [("blank", "control")]


async def test_pages_and_static_assets_are_served(stack):
    *_, server = stack
    async with httpx.AsyncClient(base_url=server.base_url) as client:
        for path in ("/display", "/control", "/web/shared/slide.js", "/web/vendor/htm-preact-standalone.mjs", "/api/state"):
            r = await client.get(path)
            assert r.status_code == 200, path


def test_slow_client_outbox_coalesces_patches_of_same_slide():
    from copilot.display.hub import Connection

    conn = Connection("display")
    conn.push({"type": "patch", "v": 1}, key=("patch", "a"))
    conn.push({"type": "deck"}, key=("deck",))
    conn.push({"type": "patch", "v": 2}, key=("patch", "a"))
    conn.push({"type": "transcript", "n": 1})
    conn.push({"type": "transcript", "n": 2})
    batch = asyncio.run(conn.next_batch())
    assert batch == [{"type": "patch", "v": 2}, {"type": "deck"}, {"type": "transcript", "n": 1}, {"type": "transcript", "n": 2}]


async def test_concerns_reach_only_the_control_view_and_overflow_is_forwarded(stack):
    from copilot.core.events import ConcernRaised, ConcernResolved, SlideOverflow

    bus, deck, hub, server = stack
    seen = []

    async def watch(e):
        seen.append(e)

    bus.subscribe("watch_overflow", watch, [SlideOverflow])
    url = f"ws://127.0.0.1:{server.port}/ws"
    concern = {"id": "c1", "claim": "Plants take in oxygen", "issue": "reversed", "status": "open",
               "kind": "factual", "confidence": 0.9, "suggested_correction": "carbon dioxide"}
    await bus.publish(ConcernRaised(concern=concern))
    await bus.drain()
    async with websockets.connect(url + "?role=display") as d, websockets.connect(url + "?role=control") as c:
        dh = await recv_until(d, lambda m: m["type"] == "hello")
        ch = await recv_until(c, lambda m: m["type"] == "hello")
        assert "concerns" not in dh and [x["id"] for x in ch["concerns"]] == ["c1"]
        await bus.publish(ConcernResolved(concern_id="c1", status="kept"))   # switched: stays listed
        msg = await recv_until(c, lambda m: m["type"] == "concern")
        assert msg["concern"]["applied"] is False and "c1" in hub.concerns
        await bus.publish(ConcernResolved(concern_id="c1", status="dismissed"))   # OK: gone
        msg = await recv_until(c, lambda m: m["type"] == "concern_resolved")
        assert msg["id"] == "c1" and hub.concerns == {}
        await deck.add(spec("s1", "one"))
        await bus.drain()
        await d.send(json.dumps({"type": "overflow", "slide_id": "s1", "version": 1}))
        await d.send(json.dumps({"type": "overflow", "slide_id": "nope"}))
        err = await recv_until(d, lambda m: m["type"] == "error")
        assert "unknown slide" in err["error"]
        await bus.drain()
        assert [(e.slide_id, e.version) for e in seen] == [("s1", 1)]
        # the display still may not send commands
        await d.send(json.dumps({"type": "command", "kind": "next"}))
        err = await recv_until(d, lambda m: m["type"] == "error")
        assert "control" in err["error"]



async def test_client_files_are_revalidated_so_updates_reach_the_browser(stack):
    bus, deck, hub, server = stack
    async with httpx.AsyncClient() as client:
        for path in ("/web/shared/slide.js", "/web/shared/slide.css", "/web/shared/ws.js"):
            r = await client.get(f"http://127.0.0.1:{server.port}{path}")
            assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", path


async def test_pages_stamp_every_client_file_with_a_version(stack):
    """A browser can never mix an old cached module with a new one: page, styles and imported modules carry ?v=."""
    bus, deck, hub, server = stack
    async with httpx.AsyncClient() as client:
        for page in ("/display", "/control"):
            html = (await client.get(f"http://127.0.0.1:{server.port}{page}")).text
            assert '<script type="importmap">' in html and '"/web/shared/slide.js": "/web/shared/slide.js?v=' in html
            assert 'src="/web/' in html and '.js?v=' in html and 'slide.css?v=' in html
            assert html.index("charset") < 1024 and html.index("importmap") < html.index("<body>")
            assert 'id="load-error"' in html or "load-error" in html               # visible error banner


async def test_misheard_words_are_corrected_without_a_card(stack):
    """User 2026-10-06: spelling / pronunciation (transcription) fixes happen silently (terminal log only); only
    factual, conceptual or formula mistakes reach the teacher as a card."""
    from copilot.core.events import ConcernRaised

    bus, deck, hub, server = stack
    heard = {"id": "t1", "claim": "6H2", "issue": "misheard", "status": "open", "kind": "transcription",
             "confidence": 0.9, "wrong": "6H2", "right": "6H2O", "applied": True}
    wrong = {"id": "f1", "claim": "Plants take in oxygen", "issue": "reversed", "status": "open", "kind": "factual",
             "confidence": 0.9, "suggested_correction": "carbon dioxide", "applied": True}
    await bus.publish(ConcernRaised(concern=heard))
    await bus.publish(ConcernRaised(concern=wrong))
    await bus.drain()
    async with websockets.connect(f"ws://127.0.0.1:{server.port}/ws?role=control") as c:
        hello = await recv_until(c, lambda m: m["type"] == "hello")
    assert [x["id"] for x in hello["concerns"]] == ["f1"] and list(hub.concerns) == ["f1"]


async def test_speech_while_paused_is_marked_in_the_transcript(stack):
    from copilot.core.events import Lifecycle, LifecycleChanged, TranscriptFinal, TranscriptSegment

    bus, deck, hub, server = stack

    async def say(text, t):
        await bus.publish(TranscriptFinal(segment=TranscriptSegment(text=text, start=t, end=t + 1)))

    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await say("Chlorophyll is green.", 1.0)
    await bus.publish(LifecycleChanged(state=Lifecycle.PAUSED))
    await say("Lunch is at twelve.", 5.0)
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await say("Light energy is absorbed.", 9.0)
    await deck.add(spec("a", "one"))
    await bus.drain()
    assert [(x["text"], x.get("dropped")) for x in hub.transcript] == [
        ("Chlorophyll is green.", None), ("Lunch is at twelve.", "paused"), ("Light energy is absorbed.", None)]
    assert "frozen" not in hub.deck
