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
