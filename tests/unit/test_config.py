from pathlib import Path

from copilot.core.config import load_config


def make_root(tmp_path: Path, default: str, local: str = "") -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "default.toml").write_text(default, encoding="utf-8")
    if local:
        (tmp_path / "config" / "local.toml").write_text(local, encoding="utf-8")
    return tmp_path


def test_precedence_default_local_env_overrides(tmp_path):
    root = make_root(
        tmp_path,
        '[app]\ntheme = "light"\nlog_level = "INFO"\n[sim]\nspeed = 1.0\n',
        '[app]\ntheme = "dark"\n',
    )
    cfg = load_config(root, environ={"COPILOT__SIM__SPEED": "5", "COPILOT__APP__LOG_LEVEL": "DEBUG"})
    assert cfg.get("app", "theme") == "dark"  # local beats default
    assert cfg.get("app", "log_level") == "DEBUG"  # env beats files
    speed = cfg.get("sim", "speed")
    assert speed == 5.0 and isinstance(speed, float)  # coerced to the default's type
    cfg2 = load_config(root, overrides={"app": {"theme": "light"}}, environ={})
    assert cfg2.get("app", "theme") == "light"  # explicit overrides beat everything


def test_project_default_config_loads():
    cfg = load_config(environ={})
    assert cfg.get("app", "theme") in ("light", "dark")
    assert cfg.get("sim", "words_per_minute") == 150
