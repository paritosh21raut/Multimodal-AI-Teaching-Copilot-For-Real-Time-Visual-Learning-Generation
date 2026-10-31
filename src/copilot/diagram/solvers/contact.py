"""Contact mechanics (F-019 §3, M1): bodies (block, box, mass) on a floor / table / incline or on each other, applied
forces, friction (static μs, kinetic μk; one μ = both), ropes over a pulley (Atwood; a block on a table pulled by a
hanging mass), a mass on a spring, a mass on a string. g = 9.8 m/s² (config/constants.toml g_earth).

    surfaces   Newton per body along its surface (+x = down the slope, or to the right on a floor). Every contact is
               stick, slip forward or slip back; each assignment (≤ 3^4) is a linear system; the consistent one with
               the most sticking contacts is kept (stick: |f| ≤ μs N; slip: the relative motion the way assumed).
    pulley     a = (m₂ − m₁) g / (m₁ + m₂), T = 2 m₁ m₂ g / (m₁ + m₂); on a table: sticks while m_h ≤ μs m_t, else
               a = (m_h − μk m_t) g / (m_t + m_h), T = m_h (g − a)
    spring     x = mg/k, T = 2π √(m/k) (oscillates about x; the amplitude on screen is illustrative)

A missing input leaves its results as symbols with their directions; nothing is guessed (RULES: never a number the
teacher did not say or Python did not compute)."""
from __future__ import annotations

import itertools
import math
from dataclasses import replace
from typing import Optional

import numpy as np

from copilot.diagram.graph import Graph
from copilot.diagram.solvers.base import Force, Motion, Results, Value
from copilot.stage.laws.base import constants

BODIES = ("block", "mass")
GROUNDS = ("floor", "incline")
EPS = 1e-9
MAX_CONTACTS = 4


def g_earth() -> float:
    return float(constants()["g_earth"]["v"])


class Contact:
    name = "contact"

    def applies(self, g: Graph) -> bool:
        return any(_ground(g, b) or _hung(g, b) for b in _bodies(g))

    def solve(self, g: Graph) -> Results:
        r = Results("contact")
        G = Value("g", g_earth(), "m/s^2", src="constant")
        r.values.append(G)
        done: set[str] = set()
        for p in [p.id for p in g.parts.values() if p.kind == "pulley"]:
            hung = [b for b in _bodies(g) if g.rels.get(b) == ("hang_from", p)]
            tied = [a for a, b in g.wires if b == p and a in g.parts and g.parts[a].kind in BODIES]
            pushed = any(g.value(b, "F") for b in hung + tied)
            if len(hung) == 2 and not tied and not pushed:
                _atwood(g, r, hung, G)
            elif len(hung) == 1 and len(tied) == 1 and _under(g, tied[0]) in g.parts \
                    and g.parts[_under(g, tied[0])].kind == "floor" and not pushed:
                _table(g, r, tied[0], hung[0], G)
            elif hung or tied:  # a rope system M1 does not solve (an incline over a pulley, a pull on a rope …)
                _unsolved(g, r, hung + tied, G, "this rope and pulley system is not solved yet (M1)" if not pushed
                          else "a force on a rope system is not solved yet (M1)")
            done |= set(hung) | set(tied)
        for b in _bodies(g):
            if b in done:
                continue
            rel = g.rels.get(b)
            if rel and rel[0] in ("hang_from", "attached_to") and rel[1] in g.parts:
                if g.parts[rel[1]].kind == "spring":
                    _spring(g, r, b, rel[1], G)
                else:
                    _hanging(g, r, b, G, rope=True)
                done.add(b)
        grounds = {}
        for b in _bodies(g):
            if b not in done and (gr := _ground_id(g, b)):
                grounds.setdefault(gr, []).append(b)
        for gr, bs in grounds.items():
            _surface(g, r, gr, bs, G)
        return r


# ---- graph helpers --------------------------------------------------------------------------------------------------
def _bodies(g: Graph) -> list[str]:
    return [p.id for p in g.parts.values() if p.kind in BODIES]


def _under(g: Graph, b: str) -> Optional[str]:
    rel = g.rels.get(b)
    return rel[1] if rel and rel[0] == "on" and rel[1] in g.parts else None


def _ground_id(g: Graph, b: str) -> Optional[str]:
    x, seen = b, set()
    while (y := _under(g, x)) and x not in seen:
        seen.add(x)
        if g.parts[y].kind in GROUNDS:
            return y
        if g.parts[y].kind not in BODIES:
            return None
        x = y
    return None


def _ground(g: Graph, b: str) -> Optional[str]:
    gr = _ground_id(g, b)
    return g.parts[gr].kind if gr else None


def _hung(g: Graph, b: str) -> bool:
    rel = g.rels.get(b)
    return bool(rel and rel[0] in ("hang_from", "attached_to"))


def _said(g: Graph, on: str, sym: str, show: Optional[str] = None, u: str = "") -> Value:
    q = g.value(on, sym)
    if q is None:
        return Value(show or sym, None, u, on, "symbol")
    return Value(show or sym, float(q["v"]), q["u"], on, "said", q=q["q"], note=q.get("note", ""))


def _mus(g: Graph, b: str) -> tuple[Value, Value]:
    """μs and μk of the contact under b: each said, or the one μ said for both, or symbols."""
    one = _said(g, b, "mu", "μ") if g.value(b, "mu") else None
    s, k = g.value(b, "mu_s"), g.value(b, "mu_k")
    mus = _said(g, b, "mu_s", "μs") if s else one or Value("μs", None, "", b, "symbol")
    muk = _said(g, b, "mu_k", "μk") if k else one or Value("μk", None, "", b, "symbol")
    return mus, muk


def _comp(sym: str, v: Optional[float], u: str, on: str, frm: list[Value], eq: str) -> Value:
    ok = v is not None and all(x.known for x in frm) and math.isfinite(v)
    return Value(sym, v if ok else None, u, on, "computed" if ok else "symbol",
                 [x.sym for x in frm] if ok else [], eq if ok else "")


def _theta(g: Graph, gr: str) -> Value:
    if g.parts[gr].kind != "incline":
        return Value("θ", 0.0, "deg", gr, "said")  # a floor: no angle, nothing printed
    return _said(g, gr, "theta", "θ", "deg")


# ---- surfaces (floor, incline, stacks) ------------------------------------------------------------------------------
_SIGN = {"floor": {"right": 1.0, "left": -1.0, "": 1.0}, "incline": {"down_slope": 1.0, "up_slope": -1.0}}


def _surface(g: Graph, r: Results, gr: str, bs: list[str], G: Value) -> None:
    kind = g.parts[gr].kind
    th = _theta(g, gr)
    th_deg = th.v if th.known else 30.0  # the drawn (illustrative) angle when not said: arrows only, no numbers
    ax = th_deg if kind == "incline" else 0.0          # screen angle of +x
    bs = _stack_order(g, bs)
    idx = {b: i for i, b in enumerate(bs)}
    n = len(bs)
    m = [_said(g, b, "m") for b in bs]
    for i, b in enumerate(bs):
        if m[i].known:
            m[i].sym = "m"
        r.values.append(m[i])
    if kind == "incline" and th.known:
        r.values.append(th)
    W = [_comp("W", m[i].v * G.v if m[i].known else None, "N", b, [m[i], G], "W = mg") for i, b in enumerate(bs)]
    r.values += W
    # applied forces along the surface (+x); a push with no way said on a floor goes right, on a slope it is unknown
    F: list[Optional[float]] = [0.0] * n
    Fv: list[Optional[Value]] = [None] * n
    unsaid = 0
    for i, b in enumerate(bs):
        q = g.value(b, "F")
        if q is None:
            continue
        sign = _SIGN[kind].get(q.get("dir") or "")
        unsaid += not q.get("dir")
        Fv[i] = _said(g, b, "F")
        r.values.append(Fv[i])
        F[i] = None if sign is None else sign * float(q["v"])
        ang = ax if (sign or -1.0) > 0 else ax + 180.0  # a push with no way said on a slope: drawn up it (as S1)
        if sign is None and q.get("dir") in ("up", "down"):
            ang = -90.0 if q["dir"] == "up" else 90.0
        r.forces.append(Force(f"F_{b}", b, "applied", Fv[i], ang, "centre", said_dir=bool(q.get("dir"))))
    dir_ok = all(f is not None for f in F) and not (unsaid and sum(1 for f in Fv if f) > 1)
    cos, sin = (math.cos(math.radians(th.v)), math.sin(math.radians(th.v))) if th.known else (None, None)
    # normal of the contact under body i: the weight of i and everything on it, times cos θ
    above = [[j for j in range(n) if _on_chain(g, bs[j], bs[i])] for i in range(n)]
    N: list[Value] = []
    for i, b in enumerate(bs):
        mass = [m[j] for j in above[i]]
        tot = sum(x.v for x in mass) if all(x.known for x in mass) else None
        v = tot * G.v * cos if tot is not None and cos is not None else None
        eq = ("N = mg cos θ" if kind == "incline" else "N = mg") if len(mass) == 1 else \
            ("N = (" + " + ".join("m" for _ in mass) + ") g" + (" cos θ" if kind == "incline" else ""))
        N.append(_comp("N", v, "N", b, mass + [G] + ([th] if kind == "incline" else []), eq))
    r.values += N
    mus, muk = zip(*[_mus(g, b) for b in bs])
    for i, b in enumerate(bs):
        for x in {id(mus[i]): mus[i], id(muk[i]): muk[i]}.values():
            if x.known:
                r.values.append(x)
    sup = [idx.get(_under(g, b), -1) for b in bs]  # -1 = the ground
    for i, b in enumerate(bs):
        r.forces.append(Force(f"W_{b}", b, "weight", W[i], 90.0, "centre"))
        r.forces.append(Force(f"N_{b}", b, "normal", N[i], ax - 90.0, "contact"))
        if sup[i] >= 0:  # Newton III: the body on top presses on the one below (drawn in the free-body view)
            r.forces.append(Force(f"N'_{b}", bs[sup[i]], "normal", replace(N[i], sym="N′"), ax + 90.0, "top",
                                  pair=True))
    known = all(x.known for x in m) and th.known and dir_ok and all(x.known for x in N) and \
        all(mus[i].known and muk[i].known for i in range(n))
    if n > MAX_CONTACTS:
        known = False
        r.notes.append(f"more than {MAX_CONTACTS} stacked bodies: not computed")
    if not known:
        for i, b in enumerate(bs):
            d = _tendency(F[i], sin, m[i]) if n == 1 else None
            if mus[i].known and muk[i].known and mus[i].v == 0 == muk[i].v:
                d = None  # frictionless: no friction arrow
            elif d is not None:
                fs = Value("f", None, "N", b, "symbol")
                r.values.append(fs)
                r.forces.append(Force(f"f_{b}", b, "friction", fs, ax + (180.0 if d > 0 else 0.0), "contact"))
            r.values.append(Value("a", None, "m/s^2", b, "symbol"))
            r.motions.append(Motion(b, "not computed"))
        r.notes.append(_missing(m, th, dir_ok, mus, muk, kind))
        return
    X = [F[i] + m[i].v * G.v * sin for i in range(n)]  # the drive along +x on each body (applied + mg sin θ)
    best = None
    for states in itertools.product(("stick", "slip+", "slip-"), repeat=n):
        sol = _regime(states, X, [x.v for x in m], [x.v for x in N], [x.v for x in mus], [x.v for x in muk], sup)
        if sol is not None:
            sticks = states.count("stick")
            if best is None or sticks > best[0]:
                best = (sticks, states, sol)
    if best is None:
        r.notes.append("no consistent friction regime (not computed)")
        return
    _, states, (a, f) = best
    for i, b in enumerate(bs):
        frm = [m[i], G, N[i]] + ([th] if kind == "incline" else []) + ([Fv[i]] if Fv[i] else [])
        st = states[i]
        fi = f[i]
        if st == "stick":
            fv = _comp("f", abs(fi), "N", b, frm + [mus[i]], "f = static friction (|f| ≤ μs N)")
        else:
            fv = _comp("f", abs(fi), "N", b, [muk[i], N[i]], "f = μk N")
        if abs(fi) > EPS:
            r.forces.append(Force(f"f_{b}", b, "friction", fv, ax if fi > 0 else ax + 180.0, "contact"))
            if sup[i] >= 0:  # the friction on the block below: the same size, the other way
                r.forces.append(Force(f"f'_{b}", bs[sup[i]], "friction", replace(fv, sym="f′"),
                                      ax + 180.0 if fi > 0 else ax, "top", pair=True))
        r.values.append(fv)
        terms = _net_terms(F[i], kind, fi, i, f, sup, a[i], Fv[i] is not None)
        av = _comp("a", abs(a[i]), "m/s^2", b, frm + [mus[i], muk[i]], f"a = ({terms}) / m")
        r.values.append(av)
        if abs(a[i]) > 1e-9:
            r.motions.append(Motion(b, "slides", abs(a[i]), ax if a[i] > 0 else ax + 180.0))
        else:
            r.motions.append(Motion(b, "at rest"))
        where = "the floor" if sup[i] < 0 and kind == "floor" else "the slope" if sup[i] < 0 else "the block below"
        r.notes.append(f"{_name(g, b)} {'sticks to' if st == 'stick' else 'slides on'} {where}")


def _regime(states: tuple[str, ...], X: list[float], m: list[float], N: list[float], mus: list[float],
            muk: list[float], sup: list[int]) -> Optional[tuple[list[float], list[float]]]:
    """One stick / slip assignment: solve for a (per body) and f (friction on each body from what it rests on);
    None if the assignment contradicts itself."""
    n = len(X)
    stick = [i for i in range(n) if states[i] == "stick"]
    fk = [0.0] * n
    for i in range(n):
        if states[i] != "stick":
            fk[i] = -(1.0 if states[i] == "slip+" else -1.0) * muk[i] * N[i]
    k = len(stick)
    A = np.zeros((n + k, n + k))
    rhs = np.zeros(n + k)
    col = {i: n + j for j, i in enumerate(stick)}
    for i in range(n):  # body i: m a = X + f_i − Σ f of the bodies resting on i
        A[i, i] = m[i]
        rhs[i] = X[i]
        if i in col:
            A[i, col[i]] -= 1.0
        else:
            rhs[i] += fk[i]
        for j in range(n):
            if sup[j] == i:
                if j in col:
                    A[i, col[j]] += 1.0
                else:
                    rhs[i] -= fk[j]
    for r_, i in enumerate(stick):  # a sticking body moves with what it rests on
        A[n + r_, i] = 1.0
        if sup[i] >= 0:
            A[n + r_, sup[i]] = -1.0
    try:
        x = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError:
        return None
    a = [float(v) for v in x[:n]]
    f = [float(x[col[i]]) if i in col else fk[i] for i in range(n)]
    tol = 1e-9
    for i in range(n):
        rel = a[i] - (a[sup[i]] if sup[i] >= 0 else 0.0)
        if states[i] == "stick" and abs(f[i]) > mus[i] * N[i] + tol:
            return None
        if states[i] == "slip+" and rel <= tol or states[i] == "slip-" and rel >= -tol:
            return None
    return a, f


def _net_terms(F: Optional[float], kind: str, fi: float, i: int, f: list[float], sup: list[int], a: float,
               pushed: bool) -> str:
    """ΣF along the motion as words of symbols ("F − f − mg sin θ")."""
    s = 1.0 if a >= 0 else -1.0
    terms = []
    if pushed and F:
        terms.append(("F", s * F))
    if kind == "incline":
        terms.append(("mg sin θ", s * 1.0))
    if abs(fi) > EPS:
        terms.append(("f", s * fi))
    for j in range(len(sup)):
        if sup[j] == i and abs(f[j]) > EPS:
            terms.append(("f′", -s * f[j]))
    if not terms:
        return "0"
    out = ""
    for k, (t, v) in enumerate(terms):
        out += (t if v >= 0 else "−" + t) if k == 0 else (f" + {t}" if v >= 0 else f" − {t}")
    return out


def _tendency(F: Optional[float], sin: Optional[float], m: Value) -> Optional[float]:
    """Which way a single body would move with no friction (+1 / −1), when the words alone decide it."""
    if F is None:
        return None
    if F == 0:  # no push: down the slope (any angle, said or not); at rest on a floor
        return 1.0 if sin is None or sin else None
    if sin is None:
        return None  # pushed on a slope whose angle is not said: which way it would move is not known
    if not sin:
        return 1.0 if F > 0 else -1.0
    if not m.known:
        return None
    return 1.0 if F + m.v * g_earth() * sin > 0 else -1.0


def _missing(m: list[Value], th: Value, dir_ok: bool, mus, muk, kind: str) -> str:
    need = []
    if not all(x.known for x in m):
        need.append("the mass")
    if kind == "incline" and not th.known:
        need.append("the angle")
    if not dir_ok:
        need.append("which way the force acts")
    if not all(x.known for x in mus) or not all(x.known for x in muk):
        need.append("the friction coefficient")
    return "not computed: " + ", ".join(need) + " not said" if need else "not computed"


def _on_chain(g: Graph, top: str, low: str) -> bool:
    """top is low, or rests (through other bodies) on low."""
    x, seen = top, set()
    while x and x not in seen:
        if x == low:
            return True
        seen.add(x)
        x = _under(g, x)
    return False


def _stack_order(g: Graph, bs: list[str]) -> list[str]:
    return sorted(bs, key=lambda b: sum(1 for _ in _chain(g, b)))


def _chain(g: Graph, b: str):
    x, seen = b, set()
    while (y := _under(g, x)) and x not in seen:
        seen.add(x)
        yield y
        x = y


def _name(g: Graph, b: str) -> str:
    p = g.parts[b]
    bodies = _bodies(g)
    if len(bodies) == 1:
        return f"the {p.label or p.kind}"
    if _under(g, b) in g.parts and g.parts[_under(g, b)].kind in BODIES:
        return f"the top {p.kind}"
    if any(_under(g, x) == b for x in bodies):
        return f"the bottom {p.kind}"
    if _hung(g, b):
        m = g.value(b, "m")
        if m and sum(1 for x in bodies if _hung(g, x)) > 1:
            return f"the {m['v']:g} kg {p.kind}"  # test40: two "hanging block" heads read alike; the said mass tells
        return f"the hanging {p.kind}"
    return f"the {p.label or p.kind}"


# ---- ropes and springs ----------------------------------------------------------------------------------------------
def _atwood(g: Graph, r: Results, hung: list[str], G: Value) -> None:
    m1, m2 = _said(g, hung[0], "m"), _said(g, hung[1], "m")
    r.values += [m1, m2]
    ok = m1.known and m2.known
    W1 = _comp("W", m1.v * G.v if m1.known else None, "N", hung[0], [m1, G], "W = mg")
    W2 = _comp("W", m2.v * G.v if m2.known else None, "N", hung[1], [m2, G], "W = mg")
    a = _comp("a", abs(m2.v - m1.v) * G.v / (m1.v + m2.v) if ok else None, "m/s^2", "", [m1, m2, G],
              "a = |m₂ − m₁| g / (m₁ + m₂)")
    T = _comp("T", 2 * m1.v * m2.v * G.v / (m1.v + m2.v) if ok else None, "N", "", [m1, m2, G],
              "T = 2 m₁ m₂ g / (m₁ + m₂)")
    r.values += [W1, W2, a, T]
    for b, W in ((hung[0], W1), (hung[1], W2)):
        r.forces += [Force(f"W_{b}", b, "weight", W, 90.0), Force(f"T_{b}", b, "tension", T, -90.0, "top")]
    if not ok:
        r.motions += [Motion(b, "not computed") for b in hung]
        r.notes.append("not computed: the masses not said")
        return
    if abs(m2.v - m1.v) < EPS:
        r.motions += [Motion(b, "at rest") for b in hung]
        r.notes.append("equal masses: at rest")
        return
    heavy, light = (hung[1], hung[0]) if m2.v > m1.v else (hung[0], hung[1])
    r.motions += [Motion(heavy, "slides", a.v, 90.0), Motion(light, "slides", a.v, -90.0)]
    r.notes.append(f"the {fmt_kg(max(m1.v, m2.v))} side goes down")


def fmt_kg(v: float) -> str:
    from copilot.simulation.base import fmt
    return f"{fmt(v)} kg"


def _table(g: Graph, r: Results, t: str, h: str, G: Value) -> None:
    mt, mh = _said(g, t, "m"), _said(g, h, "m")
    mus, muk = _mus(g, t)
    r.values += [mt, mh] + [x for x in {id(mus): mus, id(muk): muk}.values() if x.known]
    Wt = _comp("W", mt.v * G.v if mt.known else None, "N", t, [mt, G], "W = mg")
    Wh = _comp("W", mh.v * G.v if mh.known else None, "N", h, [mh, G], "W = mg")
    N = _comp("N", mt.v * G.v if mt.known else None, "N", t, [mt, G], "N = mg")
    r.values += [Wt, Wh, N]
    r.forces += [Force(f"W_{t}", t, "weight", Wt, 90.0), Force(f"N_{t}", t, "normal", N, -90.0, "contact"),
                 Force(f"W_{h}", h, "weight", Wh, 90.0)]
    ok = mt.known and mh.known and mus.known and muk.known
    if not ok:
        Tv = Value("T", None, "N", "", "symbol")
        r.forces += [Force(f"T_{t}", t, "tension", Tv, 0.0), Force(f"T_{h}", h, "tension", Tv, -90.0, "top")]
        if not (mus.known and muk.known and mus.v == 0 == muk.v):
            fs = Value("f", None, "N", t, "symbol")
            r.values.append(fs)
            r.forces.append(Force(f"f_{t}", t, "friction", fs, 180.0, "contact"))
        r.values += [Value("a", None, "m/s^2", "", "symbol"), Tv]
        r.motions += [Motion(t, "not computed"), Motion(h, "not computed")]
        r.notes.append(_missing([mt, mh], Value("θ", 0.0, "deg"), True, [mus], [muk], "floor"))
        return
    if mh.v <= mus.v * mt.v + EPS:
        a = _comp("a", 0.0, "m/s^2", "", [mt, mh, mus], "a = 0 (m_h ≤ μs m_t: it sticks)")
        T = _comp("T", mh.v * G.v, "N", "", [mh, G], "T = m_h g")
        f = _comp("f", mh.v * G.v, "N", t, [T], "f = T (static)")
        r.motions += [Motion(t, "at rest"), Motion(h, "at rest")]
        r.notes.append(f"{_name(g, t)} sticks to the table")
    else:
        a = _comp("a", (mh.v - muk.v * mt.v) * G.v / (mt.v + mh.v), "m/s^2", "", [mt, mh, muk, G],
                  "a = (m_h − μk m_t) g / (m_t + m_h)")
        T = _comp("T", mh.v * (G.v - a.v), "N", "", [mh, G, a], "T = m_h (g − a)")
        f = _comp("f", muk.v * N.v, "N", t, [muk, N], "f = μk N")
        r.motions += [Motion(t, "slides", a.v, 0.0), Motion(h, "slides", a.v, 90.0)]
        r.notes.append(f"{_name(g, t)} slides on the table")
    r.values += [f, a, T]
    r.forces += [Force(f"T_{t}", t, "tension", T, 0.0), Force(f"T_{h}", h, "tension", T, -90.0, "top")]
    if f.v and f.v > EPS:
        r.forces.append(Force(f"f_{t}", t, "friction", f, 180.0, "contact"))


def _spring(g: Graph, r: Results, b: str, s: str, G: Value) -> None:
    m, k = _said(g, b, "m"), _said(g, s, "k")
    r.values += [m, k]
    W = _comp("W", m.v * G.v if m.known else None, "N", b, [m, G], "W = mg")
    x = _comp("x", m.v * G.v / k.v if m.known and k.known and k.v > 0 else None, "m", b, [m, G, k], "x = mg / k")
    Fs = _comp("F_s", m.v * G.v if m.known and k.known else None, "N", b, [k, x], "F_s = kx = mg")
    T = _comp("T", 2 * math.pi * math.sqrt(m.v / k.v) if m.known and k.known and k.v > 0 else None, "s", b, [m, k],
              "T = 2π √(m/k)")
    r.values += [W, x, Fs, T]
    r.forces += [Force(f"W_{b}", b, "weight", W, 90.0), Force(f"S_{b}", b, "spring", Fs, -90.0, "top")]
    if T.known:
        r.motions.append(Motion(b, "oscillates", period=T.v, spring=s))
        r.notes.append("oscillates about the stretched length (amplitude illustrative)")
    else:
        r.motions.append(Motion(b, "not computed"))
        r.notes.append("not computed: " + ", ".join(w for w, v in (("the mass", m), ("k", k)) if not v.known)
                       + " not said")


def _unsolved(g: Graph, r: Results, bs: list[str], G: Value, why: str) -> None:
    """Weights (when the mass is said) and symbols for the rest: drawn, never a guessed number."""
    for b in bs:
        m = _said(g, b, "m")
        W = _comp("W", m.v * G.v if m.known else None, "N", b, [m, G], "W = mg")
        T = Value("T", None, "N", b, "symbol")
        r.values += [m, W, T] + ([_said(g, b, "F")] if g.value(b, "F") else [])
        r.forces.append(Force(f"W_{b}", b, "weight", W, 90.0))
        r.motions.append(Motion(b, "not computed"))
    r.notes.append(why)


def _hanging(g: Graph, r: Results, b: str, G: Value, rope: bool) -> None:
    m = _said(g, b, "m")
    r.values.append(m)
    W = _comp("W", m.v * G.v if m.known else None, "N", b, [m, G], "W = mg")
    T = _comp("T", W.v, "N", b, [W], "T = W (at rest)")
    r.values += [W, T]
    r.forces += [Force(f"W_{b}", b, "weight", W, 90.0), Force(f"T_{b}", b, "tension", T, -90.0, "top")]
    r.motions.append(Motion(b, "at rest"))
