"""Slide themes switchable mid-lecture (F-009 §1, user 2026-10-07): the dock's light / dark button sends `set_theme`;
the state store owns the theme and announces it; the hub repaints the projector, the students' pages and /control."""
from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, ThemeChanged
from copilot.core.state import LectureStateStore
from copilot.display.hub import DisplayHub


async def _store():
    bus = EventBus()
    store = LectureStateStore(bus, "t")
    store.attach()
    seen: list[ThemeChanged] = []

    async def grab(e):
        seen.append(e)
    bus.subscribe("test_theme", grab, [ThemeChanged])
    return bus, store, seen


async def test_set_theme_command_changes_the_lecture_theme_and_announces_it():
    bus, store, seen = await _store()
    assert store.snapshot().setup.theme == "light"
    await bus.publish(CommandReceived(command=Command(kind="set_theme", args={"theme": "dark"}, origin="control")))
    await bus.drain()
    assert store.snapshot().setup.theme == "dark"
    assert [e.theme for e in seen] == ["dark"]
    await bus.publish(CommandReceived(command=Command(kind="set_theme", args={"theme": "dark"}, origin="control")))
    await bus.drain()
    assert len(seen) == 1  # no change, no event
    await bus.close()


async def test_unknown_theme_is_ignored():
    bus, store, seen = await _store()
    await bus.publish(CommandReceived(command=Command(kind="set_theme", args={"theme": "neon"}, origin="control")))
    await bus.drain()
    assert store.snapshot().setup.theme == "light" and seen == []
    await bus.close()


async def test_hub_sends_the_new_theme_to_every_slide_page():
    bus = EventBus()
    hub = DisplayHub(bus, theme="light")
    hub.attach()
    conns = {role: hub.connect(role) for role in ("display", "control", "viewer")}
    for c in conns.values():
        await c.next_batch()  # hello
    await bus.publish(ThemeChanged(theme="dark"))
    await bus.drain()
    for role, c in conns.items():
        assert {"type": "theme", "theme": "dark"} in await c.next_batch(), role
    assert hub.hello("viewer")["theme"] == "dark"  # a page that connects later starts dark
    await bus.close()
