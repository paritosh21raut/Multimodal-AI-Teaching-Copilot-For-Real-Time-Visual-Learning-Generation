"""Projectile: a point thrown with speed u at angle θ above the horizontal from height h, uniform gravity, no air
resistance. Renderer: web/sims/projectile.js (closed-form x(t), y(t) from the drive; every printed number is from here).

    uₓ = u cos θ,  u_y = u sin θ
    x(t) = uₓ t,  y(t) = h + u_y t − ½ g t²
    time of flight  t_f = (u_y + √(u_y² + 2 g h)) / g      (h = 0: t_f = 2 u sin θ / g)
    range           R = uₓ t_f                              (h = 0: R = u² sin 2θ / g)
    maximum height  H = h + u_y² / (2 g)                    (above the ground)
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, sampled, time_graph, value_label,
)
from copilot.simulation.names import ANGLE, G

SPEED = (r"speed|velocity|initial (?:speed|velocity)|launch (?:speed|velocity)|speed of projection|"
         r"velocity of projection|thrown (?:with|at)|projected (?:with|at)|launched (?:with|at)|u")
LAUNCH_ANGLE = rf"angle of projection|elevation|launch angle|above the horizontal|with the horizontal|{ANGLE}"
HEIGHT = r"height|cliff|tower|building|table|roof|above the ground|high"

SLOTS = (
    Slot("speed_mps", "Launch speed", "u", "m/s", 0.1, 500.0, 0.5, 15.0, "speed", names=SPEED),
    Slot("angle_deg", "Launch angle", "θ", "°", 0.0, 90.0, 1.0, 45.0, "angle", names=LAUNCH_ANGLE),
    # "from a cliff" with no number: a cliff is drawn (20 m), nothing that depends on h is printed
    Slot("height_m", "Launch height", "h", "m", 0.0, 10_000.0, 0.5, 0.0, "length", absent=True, names=HEIGHT,
         present=r"\b(?:cliff|tower|building|roof|balcony|bridge|hill(?:top)?)\b", present_value=20.0),
    Slot("g", "Gravity", "g", "m/s²", 0.1, 30.0, 0.01, 9.81, "g", standard=True, names=G),
)
ELEMENTS = (
    Element("ground", "Ground"), Element("ball", "Ball"), Element("path", "Path"), Element("launch", "Launch velocity"),
    Element("components", "Velocity components"), Element("velocity", "Velocity now"), Element("range", "Range"),
    Element("peak", "Maximum height"), Element("graph", "Graph"), Element("readout", "Values"),
)


class ProjectileParams(_Model):
    speed_mps: float = Field(default=15.0, ge=0.1, le=500.0)
    angle_deg: float = Field(default=45.0, ge=0.0, le=90.0)
    height_m: float = Field(default=0.0, ge=0.0, le=10_000.0)
    g: float = Field(default=9.81, ge=0.1, le=30.0)


class ProjectileSim(SimBase):
    template: Literal["projectile"] = "projectile"
    params: ProjectileParams = Field(default_factory=ProjectileParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("speed", "angle", "height", "range", "peak", "ux", "uy")


_SLOTS = {s.name: s for s in SLOTS}


def flight(u: float, angle_deg: float, h: float, g: float) -> tuple[float, float, float]:
    """(time of flight s, range m, maximum height above the ground m)."""
    th = math.radians(angle_deg)
    ux, uy = u * math.cos(th), u * math.sin(th)
    tf = (uy + math.sqrt(uy * uy + 2 * g * h)) / g
    return tf, ux * tf, h + max(0.0, uy) ** 2 / (2 * g)


def solve(p: ProjectileParams, src: dict[str, str]) -> Solution:
    u, g, h = p.speed_mps, p.g, p.height_m
    th = math.radians(p.angle_deg)
    ux, uy = u * math.cos(th), u * math.sin(th)
    tf, R, H = flight(u, p.angle_deg, h, g)
    R = 0.0 if abs(R) < 1e-9 * max(1.0, u) else R  # straight up: back where it started (not 5e-15)
    flies = tf > 1e-9  # level along the ground (θ = 0, h = 0): no flight to print (projectile review 2026-10-17)
    said = lambda s: src.get(s, "default")  # noqa: E731
    printed = lambda s: said(s) in ("said", "teacher")  # noqa: E731
    comp_ok = known(src, _SLOTS, "speed_mps", "angle_deg")
    all_ok = comp_ok and known(src, _SLOTS, "height_m", "g") and flies
    labels = {
        "speed": value_label("u", u, "m/s", said("speed_mps"), printed("speed_mps")),
        "angle": value_label("θ", p.angle_deg, "°", said("angle_deg"), printed("angle_deg")),
        "height": value_label("h", h, "m", said("height_m"), printed("height_m")),
        "ux": value_label("u cos θ", ux, "m/s", "computed", comp_ok),
        "uy": value_label("u sin θ", uy, "m/s", "computed", comp_ok),
        "range": value_label("R", R, "m", "computed", all_ok),
        "peak": value_label("H", H, "m", "computed", all_ok),
    }
    derived = []
    if all_ok:
        derived = [
            Derived(id="tf", label="Time of flight", symbol="t_flight", value=tf, unit="s", text=f"{fmt(tf)} s"),
            Derived(id="R", label="Range", symbol="R", value=R, unit="m", text=f"{fmt(R)} m"),
            Derived(id="H", label="Maximum height", symbol="H", value=H, unit="m", text=f"{fmt(H)} m"),
            Derived(id="v_land", label="Speed on landing", symbol="v_land", value=math.sqrt(u * u + 2 * g * h),
                    unit="m/s", text=f"{fmt(math.sqrt(u * u + 2 * g * h))} m/s"),
        ]
    drive = {"ux": ux, "uy": uy, "h": h, "g": g, "tf": tf, "R": R, "H": H, "theta_deg": p.angle_deg,
             "v_max": math.sqrt(u * u + 2 * g * h)}  # the fastest it goes (it lands): the arrows' common scale
    # S2 graph: height and vertical velocity over the flight (up +), as the ball flies on the stage
    series = []
    if flies:
        ts, ys = sampled(lambda t: h + uy * t - 0.5 * g * t * t, 0.0, tf)
        _, vys = sampled(lambda t: uy - g * t, 0.0, tf)
        series = [time_graph("y_t", "Height–time", ("y", "m"), ts, ys, all_ok),
                  time_graph("vy_t", "Vertical velocity–time", ("v_y", "m/s"), ts, vys, all_ok, role="applied")]
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: ProjectileParams, src: dict[str, str]) -> list[str]:
    shown = ["ground", "ball", "path", "launch", "readout"]
    if known(src, _SLOTS, "speed_mps", "angle_deg", "height_m", "g"):
        shown += ["range", "peak"]
    return shown


TEMPLATE = Template(
    id="projectile", name="Projectile motion", subject="mechanics",
    sim=ProjectileSim, params=ProjectileParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        r"\bprojectiles?\b|\bprojectile motion\b"
        r"|\b(?:thrown|throws?|throwing|launched|launch|kicked|kicks?|fired|fires?|projected|tossed|lobbed|hit|hits)\b"
        r".*\b(?:ball|stone|object|body|particle|bullet|shell|rock|javelin|arrow|cannon ?ball|football|cricket ball)\b"
        r"|\b(?:ball|stone|bullet|cannon ?ball|rock|particle|javelin|football|shell)\b.*"
        r"\b(?:thrown|launched|kicked|fired|projected|tossed|lobbed|hit)\b", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:projectile|trajectory|parabol\w*|range|height|maximum height|time of flight|horizontal\w*|"
                       r"vertical\w*|velocity|speed|angle|degrees?|thrown|launch\w*|gravity|lands?|flight|peak|"
                       r"components?|m/s|metres?|meters?|seconds?)\b", re.IGNORECASE),
    guard=re.compile(r"\bthrown (?:out|away|off|into (?:chaos|confusion|prison|jail))|throw (?:light|an exception|an error|"
                     r"a party|up)|fired (?:from (?:the|his|her|their) jobs?|up)|launch(?:ed)? (?:a|the|its|their) "
                     r"(?:product|campaign|app|website|company|satellite|rocket)|kick(?:ed)? off|hit (?:the )?(?:market|road|"
                     r"headlines|record)|ball (?:park|game)|curve ?ball|ball and socket", re.IGNORECASE),
    results=re.compile(r"\b(?:range|maximum height|max height|greatest height|highest point|lands?|landing|travels?|"
                       r"covers?|distance|reach(?:es)?|rises? to|time of flight|flight time|impact|hits the ground|"
                       r"goes up to|goes as high as)\b", re.IGNORECASE),
    said_as=((r"\bhorizontally\b", "angle_deg", 0.0),
             (r"\b(?:vertically upwards?|vertically up|straight up(?:wards?)?)\b", "angle_deg", 90.0),
             (r"\bfrom (?:the )?ground\b|\bground level\b", "height_m", 0.0)),
    aliases=("projectile", "trajectory", "throw", "parabola", "range", "cannon", "ball"),
    carry=("g",),
    restart_on=("speed_mps", "angle_deg", "height_m", "g"),
)
