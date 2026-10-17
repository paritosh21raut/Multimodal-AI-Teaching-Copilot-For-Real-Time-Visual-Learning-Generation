"""Performance modes (F-013, user 2026-10-17): how eagerly finished speech goes to the LLM.

- **standard** (default): the lines are utterances (the speaker's pauses), a unit goes out after a 1.2 s pause and
  calls are at least 4 s apart: the F-013 S1 settings, 6.0 s median speech -> slide on the simulated check.
- **high**: every finished sentence goes out (the live speech model cuts lines at sentence ends, 0.6 s pause, 2 s
  floor): the S1b settings, titles and definitions before the sentence ends, ~45-55 % more LLM calls (same WAV:
  16-17 calls vs 11).

Both keep the instant display from the live speech model (announced titles, definitions being said, lists): that
costs no tokens. The values come from config [performance.<mode>]; the teacher's choice is kept in
data/preferences.json for the next lecture.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from copilot.core.config import Config

log = logging.getLogger(__name__)

MODES = ("standard", "high")
DEFAULT_MODE = "standard"


@dataclass(frozen=True)
class Mode:
    name: str
    pause_s: float              # gate: VAD silence after a sentence end that sends a unit
    min_call_interval_s: float  # wall-clock floor between LLM calls
    split_sentences: bool       # the live speech model cuts lines at sentence ends (the speaker does not pause)


_DEFAULTS = {
    "standard": Mode("standard", pause_s=1.2, min_call_interval_s=4.0, split_sentences=False),
    "high": Mode("high", pause_s=0.6, min_call_interval_s=2.0, split_sentences=True),
}


def mode_from_config(config: Config, name: str) -> Mode:
    base = _DEFAULTS[name if name in MODES else DEFAULT_MODE]
    sect = config.section("performance").get(base.name) or {}
    return Mode(base.name, pause_s=float(sect.get("pause_s", base.pause_s)),
                min_call_interval_s=float(sect.get("min_call_interval_s", base.min_call_interval_s)),
                split_sentences=bool(sect.get("split_sentences", base.split_sentences)))


class Preferences:
    """The teacher's choices that outlive one lecture (data/preferences.json). Only the mode for now."""

    def __init__(self, path: Path, default_mode: str = DEFAULT_MODE) -> None:
        self.path = path
        self.default_mode = default_mode if default_mode in MODES else DEFAULT_MODE

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            log.warning("preferences unreadable (%s): defaults", e)
            return {}

    @property
    def mode(self) -> str:
        m = self._read().get("mode")
        return m if m in MODES else self.default_mode

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(mode)
        data = self._read()
        data["mode"] = mode
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:  # a full disk must not stop the lecture; the mode still applies now
            log.warning("preferences not saved (%s)", e)
