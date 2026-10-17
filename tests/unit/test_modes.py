"""F-013 (user 2026-10-17): the performance switch (standard = fewer LLM calls, high = every sentence), kept for the
next lecture; and the names of saved web pages (five were all "byjus.com")."""
from copilot.app.modes import Preferences, mode_from_config
from copilot.core.bus import EventBus
from copilot.core.config import Config, load_config
from copilot.core.events import ModeChanged
from copilot.display.hub import DisplayHub
from copilot.notes.library import link_name
from copilot.understanding.service import UnderstandingSettings, apply_pace


def test_the_two_modes_from_the_shipped_config():
    config = load_config()
    std, high = mode_from_config(config, "standard"), mode_from_config(config, "high")
    assert (std.pause_s, std.min_call_interval_s, std.split_sentences) == (1.2, 4.0, False)   # the S1 settings
    assert (high.pause_s, high.min_call_interval_s, high.split_sentences) == (0.6, 2.0, True)  # the S1b settings
    assert mode_from_config(config, "turbo").name == "standard"
    assert config.get("performance", "mode") == "standard"


def test_config_values_override_the_defaults():
    config = Config({"performance": {"high": {"pause_s": 0.8}}})
    assert mode_from_config(config, "high").pause_s == 0.8
    assert mode_from_config(config, "high").min_call_interval_s == 2.0


def test_the_teachers_choice_is_kept_for_the_next_lecture(tmp_path):
    prefs = Preferences(tmp_path / "preferences.json")
    assert prefs.mode == "standard"
    prefs.set_mode("high")
    assert Preferences(tmp_path / "preferences.json").mode == "high"
    (tmp_path / "preferences.json").write_text("{broken", encoding="utf-8")
    assert Preferences(tmp_path / "preferences.json", "high").mode == "high"  # unreadable: the config default


def test_pace_changes_the_gate_the_service_already_holds():
    s = UnderstandingSettings()
    gate_cfg = s.gate
    apply_pace(s, 1.2, 4.0)
    assert gate_cfg.pause_s == 1.2 and s.min_call_interval_s == 4.0  # the same GateConfig object (mid-lecture)


async def test_set_mode_applies_saves_and_tells_control(tmp_path):
    from copilot.app.main import App

    app = App(Config({"app": {"data_dir": str(tmp_path)}}), display=False, understanding=False)
    assert app.mode.name == "standard"
    app.understanding = type("U", (), {"s": UnderstandingSettings()})()
    splits = []
    app.speech = type("S", (), {"set_split": lambda self, on: splits.append(on)})()
    seen = []

    async def grab(e):
        seen.append(e.mode)
    app.bus.subscribe("t_mode", grab, [ModeChanged])
    await app._set_mode("high")
    await app.bus.drain()
    assert app.understanding.s.gate.pause_s == 0.6 and app.understanding.s.min_call_interval_s == 2.0
    assert splits == [True] and seen == ["high"]
    assert Preferences(tmp_path / "preferences.json").mode == "high"
    await app._set_mode("nonsense")  # ignored
    await app.bus.drain()
    assert seen == ["high"] and app.mode.name == "high"
    await app.bus.close()


async def test_mode_reaches_only_the_control_view():
    bus = EventBus()
    hub = DisplayHub(bus)
    hub.attach()
    conns = {r: hub.connect(r) for r in ("display", "control", "viewer")}
    for c in conns.values():
        await c.next_batch()
    await bus.publish(ModeChanged(mode="high"))
    await bus.drain()
    assert any(m["type"] == "mode" and m["mode"] == "high" for m in await conns["control"].next_batch())
    assert hub.hello("control")["mode"] == "high" and "mode" not in hub.hello("display")
    await bus.close()


def test_saved_web_pages_are_named_by_title_or_address():
    assert link_name("https://byjus.com/biology/human-brain/", "") == "Human Brain · byjus.com"
    assert link_name("https://byjus.com/jee/photoelectric-effect/", "byjus.com") == "Photoelectric Effect · byjus.com"
    assert link_name("https://www.healthdirect.gov.au/digestive-system", "Digestive system | healthdirect") \
        == "Digestive system | healthdirect"
    assert link_name("https://example.com/", "") == "example.com"
    assert link_name("https://x.org/notes/what_is-SQL.html", "") == "What Is SQL · x.org"
