"""Sharing with students (F-008, verify round 4 step D): students get the live slide at /view and can do nothing else;
/control, /display, uploads and commands need the teacher key from outside this machine. The Cloudflare tunnel
connects from 127.0.0.1, so "outside" is recognised by the proxy headers it adds (simulated here)."""
import asyncio
import json

import httpx
import pytest
import websockets

from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, ShareChanged
from copilot.display.hub import DisplayHub
from copilot.display.server import DisplayServer, is_local
from copilot.display.share import ShareService, tunnel_url
from copilot.presentation.deck import Deck
from tests.integration.test_display_hub import free_port, recv_until, spec

KEY = "teacher-key-123"
TUNNEL = {"cf-ray": "8f1a2b3c4d-AMS", "cf-connecting-ip": "203.0.113.7", "x-forwarded-for": "203.0.113.7",
          "host": "lecture-test.trycloudflare.com"}


@pytest.fixture
async def stack():
    bus = EventBus()
    deck = Deck(bus)
    deck.attach()
    hub = DisplayHub(bus)
    hub.attach()
    server = DisplayServer(hub, port=free_port(), control_key=KEY)
    await server.start()
    yield bus, deck, hub, server
    await server.stop()
    await bus.close()


def test_only_a_direct_localhost_request_is_local():
    assert is_local("127.0.0.1", {"host": "localhost:8765"})
    assert is_local("::1", {"host": "[::1]:8765"})
    assert not is_local("127.0.0.1", TUNNEL)                                         # through the tunnel
    assert not is_local("127.0.0.1", {"host": "localhost:8765", "cf-ray": "x"})       # a proxy header
    assert not is_local("127.0.0.1", {"host": "lecture-test.trycloudflare.com"})      # addressed to the tunnel
    assert not is_local("192.168.1.20", {"host": "localhost:8765"})                  # another device (LAN)
    assert not is_local(None, {"host": "localhost"})


async def test_students_get_the_view_and_nothing_else(stack):
    bus, deck, hub, server = stack
    base = f"http://127.0.0.1:{server.port}"
    async with httpx.AsyncClient(base_url=base, headers=TUNNEL) as remote:
        assert (await remote.get("/view")).status_code == 200
        assert (await remote.get("/")).headers["location"] == "/view"
        assert (await remote.get("/display")).headers["location"] == "/view"
        r = await remote.get("/control")
        assert r.status_code == 403 and "for the teacher" in r.text
        assert (await remote.get("/control?key=wrong")).status_code == 403
        up = await remote.post("/api/upload", content=b"x", headers={"content-type": "image/png"})
        assert up.status_code == 403
    async with httpx.AsyncClient(base_url=base) as local:  # the teacher's laptop: no key needed
        assert (await local.get("/control")).status_code == 200
        assert (await local.get("/")).headers["location"] == "/control"


async def test_the_teacher_key_opens_control_from_outside(stack):
    bus, deck, hub, server = stack
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{server.port}", headers=TUNNEL) as remote:
        r = await remote.get(f"/control?key={KEY}")
        assert r.status_code == 307 and r.headers["location"] == "/control"  # the key leaves the address bar
        assert "httponly" in r.headers["set-cookie"].lower()
        assert (await remote.get("/control")).status_code == 200            # the cookie carries it from now on


async def test_websocket_roles_from_outside(stack):
    bus, deck, hub, server = stack
    await deck.add(spec("a", "one"))
    await bus.drain()
    url = f"ws://127.0.0.1:{server.port}/ws"
    hdrs = [("cf-ray", TUNNEL["cf-ray"]), ("cf-connecting-ip", TUNNEL["cf-connecting-ip"])]
    for role in ("control", "display"):
        with pytest.raises(websockets.exceptions.InvalidStatus):
            async with websockets.connect(f"{url}?role={role}", additional_headers=hdrs) as ws:
                await ws.recv()
    async with websockets.connect(f"{url}?role=control", additional_headers=hdrs + [("cookie", f"copilot_key={KEY}")]) as c:
        assert (await recv_until(c, lambda m: m["type"] == "hello"))["slides"]
    async with websockets.connect(f"{url}?role=viewer", additional_headers=hdrs) as v, \
            websockets.connect(f"{url}?role=control") as c:
        hello = await recv_until(v, lambda m: m["type"] == "hello")
        assert list(hello["slides"]) == ["a"] and hello["transcript"] == [] and "concerns" not in hello
        assert (await recv_until(c, lambda m: m["type"] == "hello"))["viewers"] == 1
        # a student's page cannot command the lecture (nor report layout overflow)
        await v.send(json.dumps({"type": "command", "kind": "next"}))
        assert (await recv_until(v, lambda m: m["type"] == "error"))["error"] == "view only"
        await v.send(json.dumps({"type": "overflow", "slide_id": "a", "version": 1}))
        assert (await recv_until(v, lambda m: m["type"] == "error"))["error"] == "view only"
        await deck.add(spec("b", "two"))  # the student sees the next slide like the projector
        await bus.drain()
        assert (await recv_until(v, lambda m: m["type"] == "patch"))["slide_id"] == "b"


async def test_the_share_state_reaches_the_teacher_only(stack):
    bus, deck, hub, server = stack
    url = f"ws://127.0.0.1:{server.port}/ws"
    async with websockets.connect(f"{url}?role=control") as c, websockets.connect(f"{url}?role=display") as d:
        await recv_until(c, lambda m: m["type"] == "hello")
        await recv_until(d, lambda m: m["type"] == "hello")
        await bus.publish(ShareChanged(state="on", url="https://lecture-test.trycloudflare.com/view"))
        await bus.drain()
        msg = await recv_until(c, lambda m: m["type"] == "share")
        assert msg["state"] == "on" and msg["url"].endswith("/view")
        with pytest.raises(asyncio.TimeoutError):
            await recv_until(d, lambda m: m["type"] == "share", timeout=0.5)


def test_the_tunnel_address_is_read_from_the_cloudflared_log():
    log = ("2026-10-06T10:00:01Z INF |  https://lecture-made-up-words.trycloudflare.com                    |")
    assert tunnel_url(log) == "https://lecture-made-up-words.trycloudflare.com"
    assert tunnel_url("INF Requesting new quick Tunnel on trycloudflare.com...") is None
    assert tunnel_url("ERR https://api.trycloudflare.com/tunnel failed") is None


async def test_a_share_that_cannot_start_says_why(tmp_path):
    """No cloudflared and nothing to download from: the teacher sees why, nothing hangs."""
    bus = EventBus()
    seen = []

    async def on(e):
        seen.append(e)

    bus.subscribe("t", on, [ShareChanged])
    share = ShareService(bus, "http://127.0.0.1:1", tmp_path, configured=str(tmp_path / "missing.exe"),
                         download_url="")
    share.find_binary = lambda: None  # type: ignore[method-assign]  # not on this PATH either
    share.attach()
    await bus.publish(CommandReceived(command=Command(kind="share_start", origin="control")))
    await bus.drain()
    await asyncio.wait_for(share._task, 5)
    await bus.drain()
    assert [e.state for e in seen] == ["starting", "starting", "failed"]
    assert "cloudflared is not installed" in seen[-1].detail
    await bus.close()
