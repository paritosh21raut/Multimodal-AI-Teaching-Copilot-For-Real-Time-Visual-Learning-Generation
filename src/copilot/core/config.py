"""Configuration: config/default.toml < config/local.toml < env COPILOT__SECTION__KEY. Secrets from .env."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Optional

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PREFIX = "COPILOT__"


def _deep_merge(base: dict, override: Mapping) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coerce(raw: str, current: Any) -> Any:
    if isinstance(current, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def _env_overrides(cfg: dict, environ: Mapping[str, str]) -> dict:
    out = cfg
    for key, raw in environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        path = key[len(ENV_PREFIX):].lower().split("__")
        if len(path) != 2:
            continue
        section, name = path
        current = cfg.get(section, {}).get(name)
        out = _deep_merge(out, {section: {name: _coerce(raw, current)}})
    return out


class Config:
    def __init__(self, data: dict) -> None:
        self._data = data

    def section(self, name: str) -> dict:
        return dict(self._data.get(name, {}))

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    @staticmethod
    def secret(name: str) -> Optional[str]:
        value = os.environ.get(name, "").strip()
        return value or None

    def as_dict(self) -> dict:
        return dict(self._data)


def load_config(
    root: Path = PROJECT_ROOT,
    overrides: Optional[Mapping] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Config:
    load_dotenv(root / ".env", override=False)
    data: dict = {}
    for name in ("default.toml", "local.toml"):
        path = root / "config" / name
        if path.exists():
            with path.open("rb") as f:
                data = _deep_merge(data, tomllib.load(f))
    data = _env_overrides(data, os.environ if environ is None else environ)
    if overrides:
        data = _deep_merge(data, overrides)
    return Config(data)
