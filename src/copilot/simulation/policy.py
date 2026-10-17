"""SimulationPolicy (F-014): what the presentation engine does with a RepresentationIntent. Pure and deterministic;
the engine owns the deck and calls this.

    show     a spoken cue + a template setup, nothing open (setting Auto): simulation mode starts on a new slide
    suggest  a /control chip "Show the <name> simulation?": a spoken cue with the setting Suggest, a strong setup
             without a cue (the scenario score) with Auto or Suggest, a cue for a template the teacher removed
    switch   another template for the open simulation ("now tilt the surface": block on a surface -> incline), on the
             same simulation slide
    update   values / the same setup for the open simulation
    end      "let's get back to the slides" while simulation mode is on
    ignore   with the reason (logged)

S1 (user 2026-10-17): every new use of a simulation makes a new simulation slide (the S0 "reopen" is gone), and only
a spoken cue shows one by itself: the score alone never does, because showing one pauses the slides.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Setting = Literal["auto", "suggest", "off"]
SETTINGS: tuple[str, ...] = ("auto", "suggest", "off")
ActionKind = Literal["show", "suggest", "switch", "update", "end", "ignore"]


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    reason: str = ""


def decide(template: str, strength: str, *, open_template: Optional[str], removed: bool = False,
           setting: Setting = "auto", mode_on: bool = False, repeated: bool = False) -> Action:
    """template: the intent's ("" = values only); strength: cue | setup | score | values | end; open_template: the
    simulation open now (None = none); removed: the teacher removed this template earlier under this topic;
    mode_on: simulation mode is running; repeated: this template's setup was heard before under this topic (the
    lecture is on it: "let us discuss the unit circle ... on the unit circle, the vertical coordinate is sine")."""
    if strength == "end":
        return Action("end", "the teacher went back to the slides") if mode_on else \
            Action("ignore", "back to the slides, but no simulation is running")
    if setting == "off" and open_template is None:
        return Action("ignore", "simulations are off")
    if strength == "values" or not template:
        return Action("update", "values for the open simulation") if open_template else \
            Action("ignore", "values, but no simulation is open")
    if open_template == template:
        return Action("update", "already open: updated")
    if open_template is not None:
        return Action("switch", f"{open_template} -> {template}")
    if strength == "setup":
        return Action("suggest", "its setup heard again in this topic") if repeated else             Action("ignore", "a setup without a spoken cue")
    if strength == "score":
        return Action("suggest", "a setup with its quantities, no spoken cue")
    if removed:
        return Action("suggest", "the teacher removed this simulation earlier in this topic")
    if setting == "suggest":
        return Action("suggest", "setting Suggest")
    return Action("show", "spoken cue + setup")
