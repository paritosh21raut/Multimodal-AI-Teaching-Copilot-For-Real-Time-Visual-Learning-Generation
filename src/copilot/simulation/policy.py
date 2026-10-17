"""SimulationPolicy (F-014): what the presentation engine does with a RepresentationIntent. Pure and deterministic;
the engine owns the deck and calls this.

    show     a spoken cue + a template setup, nothing open for it (setting Auto)
    reopen   the same template was simulated earlier under this topic: it comes back (updated), never a second one
    switch   another template for the open simulation ("now tilt the surface": block on a surface -> incline)
    update   values / the same setup for the open simulation
    ignore   with the reason (logged)

Never shown: with the setting Off; a template the teacher removed for this topic; a setup or values with nothing
open (the S1 scenario score adds the "setup + said value" path); a title slide gets a new slide instead (engine).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Setting = Literal["auto", "suggest", "off"]
ActionKind = Literal["show", "reopen", "switch", "update", "ignore"]


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    reason: str = ""


def decide(template: str, strength: str, *, open_template: Optional[str], earlier: bool, removed: bool,
           setting: Setting = "auto") -> Action:
    """template: the intent's ("" = values only); strength: cue | setup | values; open_template: the simulation
    still listening in this topic (None = none); earlier: this template was shown under this topic before (and is
    not open); removed: the teacher removed this template for this topic."""
    if setting == "off":
        return Action("ignore", "simulations are off")
    if strength == "values" or not template:
        return Action("update", "values for the open simulation") if open_template else \
            Action("ignore", "values, but no simulation is open")
    if removed:
        return Action("ignore", "the teacher removed this simulation for this topic")
    if open_template == template:
        return Action("update", "already open: updated")
    if open_template is not None:
        return Action("switch", f"{open_template} -> {template}")
    if strength != "cue":
        return Action("ignore", "a setup without a spoken cue (S1: scenario score)")
    if setting == "suggest":
        return Action("ignore", "Suggest mode: a /control chip (S1)")
    return Action("reopen", "simulated earlier in this topic") if earlier else Action("show", "spoken cue + setup")
