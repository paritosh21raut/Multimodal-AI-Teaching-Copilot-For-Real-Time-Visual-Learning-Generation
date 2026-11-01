"""Motion and relative velocity (F-019 M5): closed forms over the scene's motion parts and their said values.

    projectile     v at θ from h (the S-template's `flight`): T, R, H (above the ground), t to the top
    thrown up      v straight up: t up = v/g, H = v²/2g, T = 2v/g
    free fall      from h: t = √(2h/g), v = √(2gh); from t: h = ½gt², v = gt
    uniform        d = vt, t = d/v; accelerated (a said): v = u + at, s = ut + ½at² (u = 0 when no speed is said)
    two cars       v_rel = |v₂ − v₁| the same way, v₁ + v₂ the opposite way (the way not said: the same, noted)
    rain and man   v_rel = √(v_r² + v_m²), the umbrella tilted θ = atan(v_m / v_r) from the vertical, forward
    boat and river straight across: t = d/v_b, drift = v_river·t, v = √(v_b² + v_river²); the point directly
                   opposite: heading sin α = v_river / v_b upstream, t = d / √(v_b² − v_river²)
    circular       a_c = v²/r, T = 2πr/v, ω = v/r

World frame: metres, x right, y up, t = 0 the start. `paths` are the bodies' sampled positions (Python's numbers; the
display only scales them), `vectors` the velocity arrows. A missing input leaves the value a symbol and a note says
what is missing; nothing is printed that was not said or computed here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from copilot.diagram.graph import Graph
from copilot.diagram.solvers.base import Motion, Results, Value
from copilot.diagram.solvers.contact import g_earth
from copilot.simulation.templates.projectile import flight

KINDS = ("ball", "car", "boat", "man", "river", "rain")
MOVERS = ("ball", "car", "boat", "man")
SHOW_S = 4.0     # display seconds of a motion with no said time
KMH = 3.6


@dataclass
class Path:
    on: str
    pts: list[tuple[float, float, float]] = field(default_factory=list)  # (t, x, y) world metres
    lane: int = 0                    # cars side by side
    orbit: Optional[tuple[float, float, float, float]] = None  # circular: (cx, cy, r, period)


@dataclass
class Vec:
    id: str
    on: str                          # the body it is drawn on ("" = the triangle / the launch point)
    vx: float                        # world m/s (y up)
    vy: float
    value: Value
    role: str = "applied"            # applied (a velocity) | component | pull (relative, resultant) | normal (rain, river)
    at: str = "body"                 # body | launch | tri (the velocity triangle beside the scene)
    dashed: bool = False


def wants(g: Graph) -> bool:
    return any(p.kind in KINDS for p in g.parts.values())


class Kinematics:
    name = "motion"

    def applies(self, g: Graph) -> bool:
        return wants(g) and not any(p.kind in ("block", "mass") for p in g.parts.values())

    def solve(self, g: Graph) -> Results:
        r = Results("motion")
        G = Value("g", g_earth(), "m/s^2", src="constant")
        of = lambda k: [p.id for p in g.parts.values() if p.kind == k]  # noqa: E731
        proc = {p["target"]: p for p in g.processes}
        rain, man, river, boat, cars = of("rain"), of("man"), of("river"), of("boat"), of("car")
        if rain and man:
            _rain_man(g, r, rain[0], man[0])
        elif river and boat:
            _boat_river(g, r, boat[0], river[0], proc.get(boat[0]))
        elif len(cars) >= 2:
            _cars(g, r, cars[:2], proc)
        else:
            body = next((b for b in of("ball") + cars + boat + man if b in proc), None)
            p = proc.get(body or "")
            if p is None:
                body = next(iter(of("ball") + cars + boat + man), None)
                if body is None or not any(k[0] == body for k in g.qty):
                    r.notes.append("say how it moves (thrown, dropped, moving at …)")
                    return r
                p = {"verb": "move", "manner": None}
            verb = p["verb"]
            if verb == "circle":
                _circle(g, r, body)
            elif verb == "throw":
                r.values.append(G)
                _throw(g, r, body, p, G)
            elif verb == "fall":
                r.values.append(G)
                _fall(g, r, body, G)
            else:
                _line(g, r, body)
        for v in r.vectors:  # an arrow's symbol ("v cos θ", "−v_m") is a value of the scene too (provenance)
            if not v.value.known and not any(x.sym == v.value.sym for x in r.values):
                r.values.append(v.value)
        return r


# ---- helpers --------------------------------------------------------------------------------------------------------
def _said(g: Graph, on: str, sym: str, show: str = "", kmh: bool = False) -> Value:
    q = g.value(on, sym)
    u = {"v": "m/s", "h": "m", "t": "s", "a": "m/s^2", "r": "m", "d": "m", "theta": "deg"}[sym]
    show = show or {"theta": "θ"}.get(sym, sym)
    if q is None:
        return Value(show, None, u, on=on, src="symbol")
    if sym == "v" and (kmh or q.get("note") == "km/h"):
        return Value(show, q["v"] * KMH, "km/h", on=on, src="said", q=q["q"])
    return Value(show, q["v"], u, on=on, src="said", q=q["q"])


def _si(v: Value) -> Optional[float]:
    """A value back in SI (a speed said in km/h is shown in km/h)."""
    if not v.known:
        return None
    return v.v / KMH if v.u == "km/h" else v.v


def _out(r: Results, sym: str, v: Optional[float], u: str, on: str, frm: list[Value], eq: str, kmh: bool = False) -> Value:
    if v is None or any(not f.known for f in frm):
        val = Value(sym, None, u, on=on, src="symbol")
    elif kmh and u == "m/s":
        val = Value(sym, v * KMH, "km/h", on=on, frm=[f.sym for f in frm], eq=eq)
    else:
        val = Value(sym, v, u, on=on, frm=[f.sym for f in frm], eq=eq)
    r.values.append(val)
    return val


def _steps(T: float, dt: float = 1 / 30) -> list[float]:
    if not (T > 0 and dt > 0):
        return [0.0]
    n = max(1, min(240, int(math.ceil(T / dt))))
    return [T * i / n for i in range(n + 1)]


def _missing(r: Results, vals: list[Value], what: str) -> None:
    lost = [v.sym for v in vals if not v.known]
    if lost:
        r.notes.append(f"say {', '.join(lost)} to compute {what}")


# ---- cases ----------------------------------------------------------------------------------------------------------
def _throw(g: Graph, r: Results, b: str, p: dict, G: Value) -> None:
    v = _said(g, b, "v")
    h = _said(g, b, "h")
    manner = p.get("manner")
    q = g.value(b, "theta")
    # the later of the two wins: "throw it straight up" after "at 30 degrees" is a throw up (and the other way)
    th = _said(g, b, "theta") if q is not None and (manner not in ("up", "horizontal")
                                                     or q.get("seq", 0) > p.get("seq", 0)) else Value("θ", None, "deg", b, "symbol")
    r.values += [v] + ([th] if th.known else []) + ([h] if h.known else [])
    up = manner == "up" and not th.known
    if manner == "horizontal" and not th.known:
        ang = 0.0
    elif up:
        ang = 90.0
    else:
        ang = th.v if th.known else None
    h0 = h.v if h.known else 0.0
    gv = G.v
    no_h = ang == 0.0 and not h.known
    if not v.known or ang is None or no_h:
        _missing(r, [v] + ([th] if ang is None else []) + ([h] if no_h else []), "the flight")
        r.motions.append(Motion(b, "not computed"))
        sym = [v] + ([th] if ang is None else [])
        for s in ("T", "R", "H"):
            r.values.append(Value(s, None, "s" if s == "T" else "m", on=b, src="symbol"))
        r.vectors.append(Vec("v0", "", 0.7 if ang is None else math.cos(math.radians(ang)),
                             0.7 if ang is None else math.sin(math.radians(ang)), sym[0], at="launch"))
        r.paths.append(Path(b, [(0.0, 0.0, h0)]))
        return
    u = _si(v)
    tf, rng, hmax = flight(u, ang, h0, gv)
    ux, uy = u * math.cos(math.radians(ang)), u * math.sin(math.radians(ang))
    frm = [v] + ([th] if th.known else []) + ([h] if h.known else []) + [G]
    if up:
        _out(r, "t_up", uy / gv, "s", b, [v, G], "t = v/g")
        _out(r, "H", hmax, "m", b, frm, "H = v²/2g" if not h.known else "H = h + v²/2g")
        _out(r, "T", tf, "s", b, frm, "T = 2v/g" if not h.known else "T: y(T) = 0")
    else:
        _out(r, "T", tf, "s", b, frm, "T = 2v sin θ / g" if not h.known and ang else "T: y(T) = 0")
        _out(r, "R", rng, "m", b, frm, "R = v² sin 2θ / g" if not h.known and ang else "R = v cos θ · T")
        _out(r, "H", hmax, "m", b, frm, "H = v² sin² θ / 2g" if not h.known else "H = h + (v sin θ)² / 2g")
    r.paths.append(Path(b, [(t, ux * t, max(0.0, h0 + uy * t - gv * t * t / 2)) for t in _steps(tf)]))
    r.vectors.append(Vec("v0", "", ux, uy, v, at="launch"))
    if 0 < ang < 90:
        r.vectors += [Vec("ux", "", ux, 0.0, Value("v cos θ", None, "m/s", src="symbol"), "component", "launch", True),
                      Vec("uy", "", 0.0, uy, Value("v sin θ", None, "m/s", src="symbol"), "component", "launch", True)]
    r.motions.append(Motion(b, "flies", a=gv, ang=90.0))


def _fall(g: Graph, r: Results, b: str, G: Value) -> None:
    h, t = _said(g, b, "h"), _said(g, b, "t")
    gv = G.v
    if h.known:
        r.values.append(h)
        T = math.sqrt(2 * h.v / gv)
        _out(r, "t", T, "s", b, [h, G], "t = √(2h/g)")
        _out(r, "v", math.sqrt(2 * gv * h.v), "m/s", b, [h, G], "v = √(2gh)")
        H = h.v
    elif t.known:
        r.values.append(t)
        T, H = t.v, gv * t.v ** 2 / 2
        _out(r, "h", H, "m", b, [t, G], "h = ½ g t²")
        _out(r, "v", gv * T, "m/s", b, [t, G], "v = g t")
    else:
        r.notes.append("say the height (or the time) to compute the fall")
        r.motions.append(Motion(b, "not computed"))
        r.paths.append(Path(b, [(0.0, 0.0, 1.0)]))
        return
    r.paths.append(Path(b, [(s, 0.0, H - gv * s * s / 2) for s in _steps(T)]))
    r.motions.append(Motion(b, "falls", a=gv, ang=90.0))


def _line(g: Graph, r: Results, b: str, sign: float = 1.0) -> None:
    """One body along a straight line: uniform, or accelerated when a is said."""
    kmh = (g.value(b, "v") or {}).get("note") == "km/h"
    v, t, d, a = _said(g, b, "v", kmh=kmh), _said(g, b, "t"), _said(g, b, "d"), _said(g, b, "a")
    r.values += [x for x in (v, a, t, d) if x.known]
    if a.known:
        u = _si(v) or 0.0
        frm0 = [v] if v.known else []
        if t.known:
            T = t.v
            _out(r, "v_end", u + a.v * T, "m/s", b, frm0 + [a, t], "v = u + a t", kmh)
            _out(r, "s", u * T + a.v * T * T / 2, "m", b, frm0 + [a, t], "s = u t + ½ a t²")
        elif d.known:
            vf = math.sqrt(max(0.0, u * u + 2 * a.v * d.v))
            T = (vf - u) / a.v if a.v else d.v / u if u else SHOW_S
            _out(r, "v_end", vf, "m/s", b, frm0 + [a, d], "v² = u² + 2 a s", kmh)
            _out(r, "t", T, "s", b, frm0 + [a, d], "t = (v − u)/a")
        else:
            T = SHOW_S
            r.notes.append("say a time or a distance to compute v")
        r.paths.append(Path(b, [(s, sign * (u * s + a.v * s * s / 2), 0.0) for s in _steps(T)]))
        r.motions.append(Motion(b, "accelerates", a=a.v))
        r.vectors.append(Vec("v_" + b, b, sign, 0.0, v if v.known else Value("v", None, "m/s", src="symbol")))
        return
    vs = _si(v)
    if vs is None:
        r.notes.append("say its speed to compute the motion")
        r.paths.append(Path(b, [(0.0, 0.0, 0.0)]))
        r.motions.append(Motion(b, "not computed"))
        r.vectors.append(Vec("v_" + b, b, sign, 0.0, v))
        return
    if t.known:
        _out(r, "d", vs * t.v, "m", b, [v, t], "d = v t")
        T = t.v
    elif d.known:
        T = _out(r, "t", d.v / vs if vs else None, "s", b, [v, d], "t = d / v").v or SHOW_S
    else:
        T = SHOW_S
    r.paths.append(Path(b, [(s, sign * vs * s, 0.0) for s in _steps(T)]))
    r.motions.append(Motion(b, "moves", a=0.0))
    r.vectors.append(Vec("v_" + b, b, sign * vs, 0.0, v))


def _cars(g: Graph, r: Results, cars: list[str], proc: dict) -> None:
    kmh = all((g.value(c, "v") or {}).get("note") == "km/h" for c in cars)
    v1, v2 = (_said(g, c, "v", f"v_{i}") for i, c in enumerate(cars, 1))
    r.values += [v1, v2]
    opp = (proc.get(cars[1]) or {}).get("manner") == "opposite"
    said_way = opp or (proc.get(cars[1]) or {}).get("manner") == "same"
    a, b = _si(v1), _si(v2)
    if opp:
        rel = _out(r, "v_rel", a + b if a is not None and b is not None else None, "m/s", "", [v1, v2],
                   "v_rel = v₁ + v₂ (opposite ways)", kmh)
    else:
        rel = _out(r, "v_rel", abs(b - a) if a is not None and b is not None else None, "m/s", "", [v1, v2],
                   "v_rel = v₂ − v₁ (same way)" if (b or 0) >= (a or 0) else "v_rel = v₁ − v₂ (same way)", kmh)
    if not said_way and rel.known:
        r.notes.append("the way is not said: the same way is drawn")
    _missing(r, [v1, v2], "the relative velocity")
    T = SHOW_S
    sa, sb = a or 0.0, b or 0.0
    far = (sa + sb) * T if opp else 0.0
    r.paths.append(Path(cars[0], [(s, sa * s, 0.0) for s in _steps(T)], lane=0))
    r.paths.append(Path(cars[1], [(s, far - sb * s if opp else sb * s, 0.0) for s in _steps(T)], lane=1))
    r.vectors.append(Vec("v_1", cars[0], sa or 1.0, 0.0, v1))
    r.vectors.append(Vec("v_2", cars[1], -(sb or 1.0) if opp else sb or 1.0, 0.0, v2))
    for c in cars:
        r.motions.append(Motion(c, "moves", a=0.0))


def _rain_man(g: Graph, r: Results, rain: str, man: str) -> None:
    vr, vm = _said(g, rain, "v", "v_r"), _said(g, man, "v", "v_m")
    r.values += [vr, vm]
    a, b = _si(vr), _si(vm)
    ok = a is not None and b is not None
    rel = _out(r, "v_rel", math.hypot(a, b) if ok else None, "m/s", "", [vr, vm], "v_rel = √(v_r² + v_m²)")
    th = _out(r, "θ", math.degrees(math.atan2(b, a)) if ok and a > 0 else None, "deg", "", [vr, vm],
              "tan θ = v_m / v_r (from the vertical)")
    _missing(r, [vr, vm], "the umbrella angle")
    if th.known:
        r.notes.append("hold the umbrella tilted forward by θ")
    sm = b or 0.0
    r.paths.append(Path(man, [(s, sm * s, 0.0) for s in _steps(SHOW_S)]))
    r.motions.append(Motion(man, "moves" if b else "not computed", a=0.0))
    r.extra["tilt"] = th.v if th.known else 0.0
    # the triangle: rain down, the man's velocity reversed (what the man feels), the rain as the man sees it
    r.vectors += [Vec("vr", "", 0.0, -(a or 1.0), vr, "normal", "tri"),
                  Vec("vm", "", -(b or 0.75), 0.0, Value("−v_m", None, "m/s", src="symbol"), "component", "tri", True),
                  Vec("vrel", "", -(b or 0.75), -(a or 1.0), rel, "pull", "tri")]
    r.vectors.append(Vec("v_man", man, b or 0.75, 0.0, vm))


def _boat_river(g: Graph, r: Results, boat: str, river: str, p: Optional[dict]) -> None:
    vb, vr, d = _said(g, boat, "v", "v_b"), _said(g, river, "v", "v_river"), _said(g, river, "d")
    r.values += [vb, vr] + ([d] if d.known else [])
    short = (p or {}).get("manner") == "short"
    a, b = _si(vb), _si(vr)
    ok = a is not None and b is not None
    if short:
        if ok and a > b:
            _out(r, "α", math.degrees(math.asin(b / a)), "deg", boat, [vb, vr], "sin α = v_river / v_b (upstream)")
            across = math.sqrt(a * a - b * b)
            _out(r, "v", across, "m/s", boat, [vb, vr], "v = √(v_b² − v_river²)")
            T = _out(r, "t", d.v / across if d.known else None, "s", boat, [d, vb, vr], "t = d / v").v
            hx, hy = -b, across  # heading upstream (the river flows to +x)
            r.notes.append("head upstream at α to reach the point opposite")
        else:
            if ok:
                r.notes.append("the river is as fast as the boat or faster: it cannot reach the point opposite")
            _missing(r, [vb, vr], "the heading")
            T, hx, hy, across = None, 0.0, a or 1.0, a or 1.0
    else:
        T = _out(r, "t", d.v / a if d.known and a else None, "s", boat, [d, vb], "t = d / v_b").v
        _out(r, "x", b * T if T is not None and b is not None else None, "m", boat, [vr, d, vb],
                     "x = v_river · t (drift)")
        _out(r, "v", math.hypot(a, b) if ok else None, "m/s", boat, [vb, vr], "v = √(v_b² + v_river²)")
        hx, hy, across = 0.0, a or 1.0, a or 1.0
        _missing(r, [vb, vr] + ([d] if not d.known else []), "the crossing")
    W = d.v if d.known else 100.0
    Tm = T or (W / across if across else SHOW_S)
    vx, vy = hx + (b or 0.0), hy
    r.paths.append(Path(boat, [(s, vx * s * (W / (vy * Tm)) if vy else 0.0, vy * s * (W / (vy * Tm)) if vy else 0.0)
                              for s in _steps(Tm, Tm / 120)]))
    r.extra["width"] = W
    r.vectors += [Vec("vb", boat, hx, hy, vb),
                  Vec("vriver", river, b or 1.0, 0.0, vr, "normal"),
                  Vec("vres", boat, vx, vy, next((x for x in r.values if x.sym == "v" and x.on == boat),
                                                 Value("v", None, "m/s", src="symbol")), "pull", dashed=True)]
    r.motions.append(Motion(boat, "crosses" if T else "not computed"))


def _circle(g: Graph, r: Results, b: str) -> None:
    v, rad = _said(g, b, "v"), _said(g, b, "r")
    r.values += [x for x in (v, rad) if x.known]
    vs = _si(v)
    ok = vs is not None and rad.known and vs > 0
    _out(r, "a_c", vs * vs / rad.v if ok else None, "m/s^2", b, [v, rad], "a_c = v² / r")
    T = _out(r, "T", 2 * math.pi * rad.v / vs if ok else None, "s", b, [v, rad], "T = 2πr / v").v
    _out(r, "ω", vs / rad.v if ok else None, "rad/s", b, [v, rad], "ω = v / r")
    _missing(r, [v, rad], "the circular motion")
    R = rad.v if rad.known else 1.0
    r.paths.append(Path(b, [(0.0, 0.0, R)], orbit=(0.0, 0.0, R, T or 4.0)))
    r.vectors += [Vec("v_c", b, 1.0, 0.0, v if v.known else Value("v", None, "m/s", src="symbol")),
                  Vec("a_c", b, 0.0, -1.0, next(x for x in r.values if x.sym == "a_c"), "pull")]
    r.motions.append(Motion(b, "circles", period=T))
