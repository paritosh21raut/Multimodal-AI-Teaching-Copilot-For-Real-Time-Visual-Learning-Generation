"""Shortest-path routing, Dijkstra (F-014 S4). Renderer: web/sims/routing.js.

A small network said link by link ("A to B costs 4", "the link between B and D has cost 5"): nodes are single capital
letters A-H, at most 8 nodes and 14 links, costs positive, links both ways (user 2026-10-20). With a source said
("the shortest path from A to F"), Dijkstra's algorithm runs as a process (the S3 step model): one step per node it
visits, in its order (the unvisited node with the smallest distance; a tie goes to the earlier letter), then, with a
target said, the path step (the path found, packets sent along it). The steps come from the values (Template.step_defs).

    visit u: for each neighbour v not yet visited: d(v) = min(d(v), d(u) + cost(u, v)), via u when it improves

    A-B 4, A-C 2, B-C 1, B-D 5, C-D 8, C-E 10, D-E 2, D-F 6, E-F 2 from A:
      visit A 0 (B 4, C 2), C 2 (B 3 via C, D 10, E 12), B 3 (D 8 via B), D 8 (E 10 via D, F 14), E 10 (F 12 via E),
      F 12; path A → C → B → D → E → F, cost 12

Nothing is printed from a default: no links said = a sample network drawn without costs and without steps; no source
said = the costs only. The graph, the table and the steps are SimEvents (kind node / edge / dist / visit / relax / path,
`step` = the step they belong to, -1 = before the first); every printed text is made here.
"""
from __future__ import annotations

import heapq
import re
from typing import Any, Literal, Optional

from pydantic import Field, field_validator

from copilot.simulation.values import spoken_number
from copilot.simulation.base import (
    Derived, Element, SimBase, SimEvent, SimLabel, Solution, StepDef, Template, _Model, fmt,
)

MAX_NODES, MAX_EDGES, MAX_COST = 8, 14, 999.0
NODE = r"(?-i:[A-H])"
SAMPLE = "A-B:1,A-C:1,B-C:1,B-D:1,C-E:1,D-E:1,D-F:1,E-F:1"  # drawn without costs while no link is said
ELEMENTS = (
    Element("graph", "Network"), Element("costs", "Link costs"), Element("table", "Distance table"),
    Element("path", "Shortest path"), Element("packets", "Packets on the path"), Element("readout", "Values"),
)


def parse_edges(s: str) -> dict[tuple[str, str], float]:
    """"A-B:4,B-C:1" (or "A-B 4; B C 1") -> {("A", "B"): 4.0, ...}, the pair in letter order; raises ValueError."""
    out: dict[tuple[str, str], float] = {}
    for part in re.split(r"[,;\n]+", s.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"([A-Ha-h])\s*[-–\s]\s*([A-Ha-h])\s*[:=\s]\s*(\d+(?:\.\d+)?)", part)
        if m is None:
            raise ValueError(f"a link is a pair of letters A-H and a cost: {part!r}")
        a, b, c = m.group(1).upper(), m.group(2).upper(), float(m.group(3))
        if a == b or not 0 < c <= MAX_COST:
            raise ValueError(f"bad link {part!r}")
        out[(min(a, b), max(a, b))] = c
    nodes = {n for e in out for n in e}
    if len(nodes) > MAX_NODES or len(out) > MAX_EDGES:
        raise ValueError(f"at most {MAX_NODES} nodes and {MAX_EDGES} links")
    return out


def edges_text(e: dict[tuple[str, str], float]) -> str:
    return ",".join(f"{a}-{b}:{fmt(c)}" for (a, b), c in sorted(e.items()))


class RoutingParams(_Model):
    edges: str = ""          # "A-B:4,A-C:2": the links said (canonical, letter order)
    source: str = ""         # a node letter, "" = not said
    target: str = ""

    @field_validator("edges")
    @classmethod
    def _edges(cls, v: str) -> str:
        return edges_text(parse_edges(v)) if v.strip() else ""

    @field_validator("source", "target")
    @classmethod
    def _node(cls, v: str) -> str:
        v = v.strip().upper()
        if v and not re.fullmatch(r"[A-H]", v):
            raise ValueError("a node is one letter A-H")
        return v


class RoutingSim(SimBase):
    template: Literal["routing"] = "routing"
    params: RoutingParams = Field(default_factory=RoutingParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("source", "target")


def dijkstra(e: dict[tuple[str, str], float], src: str, dst: str = ""):
    """The visits in order: [(u, d(u), [(v, old, new, improved), ...], table after)], + prev map."""
    adj: dict[str, list[tuple[str, float]]] = {}
    for (a, b), c in e.items():
        adj.setdefault(a, []).append((b, c))
        adj.setdefault(b, []).append((a, c))
    nodes = sorted(adj)
    dist = {n: float("inf") for n in nodes}
    prev: dict[str, str] = {}
    dist[src] = 0.0
    done: set[str] = set()
    heap = [(0.0, src)]
    visits = []
    while heap:
        du, u = heapq.heappop(heap)
        if u in done or du > dist[u]:
            continue
        done.add(u)
        relax = []
        for v, c in sorted(adj[u]):
            if v in done:
                continue
            old, new = dist[v], du + c
            better = new < old - 1e-12
            if better:
                dist[v], prev[v] = new, u
                heapq.heappush(heap, (new, v))
            relax.append((v, old, new, better))
        visits.append((u, du, relax, dict(dist)))
        if u == dst:
            break
    return visits, prev, nodes


def path_to(prev: dict[str, str], src: str, dst: str) -> list[str]:
    if dst != src and dst not in prev:
        return []
    out = [dst]
    while out[-1] != src:
        out.append(prev[out[-1]])
    return out[::-1]


def _said(src: dict[str, str], name: str) -> bool:
    return src.get(name, "default") in ("said", "teacher")


def _visit_words(n: str) -> str:
    return (rf"\b(?:visit\w*|pick\w*|choos\w*|chose|select\w*|take|took|move\w* (?:on )?to|explor\w*|process\w*|"
            rf"expand\w*|finali[sz]\w*|next (?:is|comes))\s+(?:(?:the )?(?:node|vertex|router)\s+)?{NODE}(?![\w-])|"
            rf"(?<![\w-]){NODE}\s+is\s+(?:now\s+)?(?:visited|finali[sz]ed|done|permanent|marked)\b|"
            rf"\bsmallest (?:distance|cost)\b[^.;]{{0,30}}(?<![\w-]){NODE}(?![\w-])").replace(NODE, rf"(?-i:{n})")


PATH_WORDS = (r"\b(?:the )?shortest (?:path|route) (?:is|goes|from \S+ to \S+ is)\b|"
              r"\b(?:so|therefore|hence) the (?:path|route) is\b")


def step_defs(p: RoutingParams, src: dict[str, str]) -> tuple[StepDef, ...]:
    if not p.edges or not p.source or not (_said(src, "edges") and _said(src, "source")):
        return ()
    e = parse_edges(p.edges)
    if p.source not in {n for k in e for n in k}:
        return ()
    visits, prev, _ = dijkstra(e, p.source, p.target if _said(src, "target") else "")
    out = [StepDef(f"v_{u}", f"Visit {u} (distance {fmt(du)})", _visit_words(u)) for u, du, _, _ in visits]
    if p.target and _said(src, "target") and p.target in {n for k in e for n in k}:
        out.append(StepDef("path", "Shortest path", PATH_WORDS))
    return tuple(out)


def solve(p: RoutingParams, src: dict[str, str]) -> Solution:
    said_edges = bool(p.edges) and _said(src, "edges")
    e = parse_edges(p.edges) if said_edges else parse_edges(SAMPLE)
    nodes = sorted({n for k in e for n in k})
    root = p.source if p.source in nodes else nodes[0]
    # layers by hops from the source (left to right), nodes in a layer spread up and down
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for a, b in e:
        adj[a].add(b)
        adj[b].add(a)
    layer = {root: 0}
    q = [root]
    while q:
        u = q.pop(0)
        for v in sorted(adj[u]):
            if v not in layer:
                layer[v] = layer[u] + 1
                q.append(v)
    top = max(layer.values()) + 1
    for n in nodes:
        layer.setdefault(n, top)
    cols: dict[int, list[str]] = {}
    for n in nodes:
        cols.setdefault(layer[n], []).append(n)
    ncol = max(cols) + 1
    events: list[SimEvent] = []
    for k, col in sorted(cols.items()):
        x = 90 + (560 * k / (ncol - 1) if ncol > 1 else 280)
        for i, n in enumerate(col):
            y = 380 + (i - (len(col) - 1) / 2) * min(190, 380 / max(1, len(col) - 1) if len(col) > 1 else 0)
            # in a column of 3+, every other node steps aside: a link between two of them passes the one between
            dx = (-1 if i % 2 else 1) * 44 if len(col) > 2 else 0
            events.append(SimEvent(kind="node", a=n, t=x + dx, t2=y))
    for (a, b), c in sorted(e.items()):
        events.append(SimEvent(kind="edge", a=a, b=b, label=fmt(c) if said_edges else ""))
    labels = {"source": SimLabel(symbol=""), "target": SimLabel(symbol="")}
    derived: list[Derived] = []
    run = said_edges and _said(src, "source") and p.source in nodes
    if _said(src, "source") and p.source:
        labels["source"] = SimLabel(symbol="source", text=p.source, source=src["source"])  # type: ignore[arg-type]
    if _said(src, "target") and p.target:
        labels["target"] = SimLabel(symbol="target", text=p.target, source=src["target"])  # type: ignore[arg-type]
    if run:
        dst = p.target if _said(src, "target") else ""
        visits, prev, _ = dijkstra(e, p.source, dst)
        inf = lambda x: "∞" if x == float("inf") else fmt(x)  # noqa: E731
        start = {n: (0.0 if n == p.source else float("inf")) for n in nodes}
        for n in nodes:
            events.append(SimEvent(kind="dist", step=-1, a=n, label=inf(start[n])))
        via: dict[str, str] = {}
        for k, (u, du, relax, table) in enumerate(visits):
            events.append(SimEvent(kind="visit", step=k, a=u, label=inf(du)))
            changed = set()
            for v, old, new, better in relax:
                c = e[(min(u, v), max(u, v))]
                events.append(SimEvent(kind="relax", step=k, a=u, b=v, n=1 if better else 0,
                                       label=f"{fmt(du)} + {fmt(c)} = {fmt(new)}" + ("" if better else
                                                                                     f" ≥ {inf(old)}")))
                if better:
                    via[v] = u
                    changed.add(v)
            for n in nodes:
                events.append(SimEvent(kind="dist", step=k, a=n, b=via.get(n, ""), n=1 if n in changed else 0,
                                       label=inf(table.get(n, float("inf")))))
        if dst and dst in nodes:
            route = path_to(prev, p.source, dst)
            k = len(visits)
            for a, b in zip(route, route[1:]):
                events.append(SimEvent(kind="path", step=k, a=a, b=b))
            if route:
                derived.append(Derived(id="path", label="Shortest path", symbol="path", value=float(len(route)),
                                       text=" → ".join(route)))
                cost = sum(e[(min(a, b), max(a, b))] for a, b in zip(route, route[1:]))
                derived.append(Derived(id="cost", label="Its cost", symbol="cost", value=cost, text=fmt(cost)))
            else:
                derived.append(Derived(id="path", label="Shortest path", symbol="path", value=0.0,
                                       text=f"{dst} cannot be reached"))
    drive = {"nodes": float(len(nodes)), "said": 1.0 if said_edges else 0.0, "still_t": 0.0}
    return Solution(drive=drive, labels=labels, derived=derived, events=events)


def default_shown(p: RoutingParams, src: dict[str, str]) -> list[str]:
    shown = ["graph"]
    if p.edges and _said(src, "edges"):
        shown.append("costs")
    if _said(src, "source"):
        shown.append("table")
    if _said(src, "target"):
        shown += ["path", "packets", "readout"]
    return shown


# ---- speech: links with their costs, the source and the target, a link going down, notices -------------------------
_PAIR = re.compile(rf"(?<![\w-])({NODE})\s*(?:-|–|to|and)\s*({NODE})(?![\w-])|"
                   rf"\b(?i:edge|link)\s+({NODE})({NODE})(?![\w-])")
_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w]|\.\d)|\b(one|two|three|four|five|six|seven|eight|nine|ten|"
                  r"eleven|twelve|fifteen|twenty)\b", re.IGNORECASE)
_COUNTED = re.compile(r"^\s*(?:links?|edges?|nodes?|routers?|vertices|hops?)\b", re.IGNORECASE)  # "9 links": a count
_RESULT = re.compile(r"\b(?:shortest|total|path|route|via|through|hops?|distances?|improv\w*|neighbou?rs?|gets?)\b",
                     re.IGNORECASE)  # results of the run, not a link's cost
_FROM_TO = re.compile(rf"\bfrom\s+(?:(?:node|router|vertex)\s+)?({NODE})\s+to\s+(?:(?:node|router|vertex)\s+)?({NODE})"
                      rf"(?![\w-])", re.IGNORECASE)
_ROUTE = re.compile(r"\b(?:shortest|best|cheapest|least[- ]cost)\b|\b(?:send|sends|sending|sent)\b[^.;]{0,20}\bpackets?\b"
                    r"|\bpackets?\b[^.;]{0,20}\b(?:send|sent|travel\w*)\b|\bfind (?:the )?(?:path|route)\b", re.IGNORECASE)
_COSTLY = re.compile(r"\b(?:cost|costs|distance|weight|link|edge)\b[^.;]*$", re.IGNORECASE)
_SOURCE = re.compile(rf"\b(?:source|start(?:ing)?(?: node| point)?)\s+(?:is|at|from|=)?\s*(?:(?:node|router)\s+)?"
                     rf"({NODE})(?![\w-])|\bstart(?:ing)? (?:at|from)\s+(?:(?:node|router)\s+)?({NODE})(?![\w-])|"
                     rf"\b(?:let|take|make|choose)\s+(?:(?:node|router)\s+)?({NODE})\s+(?:be|as)\s+(?:the\s+)?source\b",
                     re.IGNORECASE)
_TARGET = re.compile(rf"\b(?:destination|target)(?: node)?\s+(?:is|=)?\s*(?:(?:node|router)\s+)?({NODE})(?![\w-])|"
                     rf"\bto reach\s+(?:(?:node|router)\s+)?({NODE})(?![\w-])", re.IGNORECASE)
_DOWN = re.compile(rf"\b(?:link|edge|connection|cable)\s+(?:between\s+)?({NODE})\s*(?:-|–|to|and)\s*({NODE})(?![\w-])"
                   r"[^.;]{0,30}?\b(?:fails|failed|goes down|went down|is down|breaks|broke|is (?:removed|cut))\b|"
                   rf"\b(?:remove|cut|break|delete)\s+the\s+(?:link|edge|connection)\s+(?:between\s+)?({NODE})\s*"
                   rf"(?:-|–|to|and)\s*({NODE})(?![\w-])", re.IGNORECASE)
_NOT_DRAWN = (
    (re.compile(r"\bbellman[- ]?ford\b|\bdistance[- ]vector\b|\bRIP\b|\bcount(?:ing)? to infinity\b", re.I),
     "Distance-vector routing (Bellman-Ford) is not drawn: the simulation runs Dijkstra (link state)"),
    (re.compile(r"\bBGP\b|\bautonomous systems?\b", re.I), "Routing between networks (BGP) is not drawn"),
    (re.compile(r"\bnegative (?:costs?|weights?|edges?)\b", re.I), "Negative costs are not drawn: Dijkstra needs costs above 0"),
    (re.compile(r"\b(?:A\*|a star|bfs|breadth[- ]first|depth[- ]first|dfs|floyd|prim|kruskal|spanning tree)\b", re.I),
     "Only Dijkstra's shortest path is drawn"),
)


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    state = state or {}
    out: list[tuple[str, Any, str, int]] = []
    try:
        e = parse_edges(state.get("edges") or "")
    except ValueError:
        e = {}
    before = dict(e)
    first = -1
    for m in _DOWN.finditer(line):
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if e.pop((min(a, b), max(a, b)), None) is not None and first < 0:
            first = m.start()
    pairs = list(_PAIR.finditer(line))
    for i, m in enumerate(pairs):
        end = pairs[i + 1].start() if i + 1 < len(pairs) else len(line)
        clause = line[m.end():end]
        stop = re.search(r"[.;](?!\d)", clause)
        clause = clause[:stop.start()] if stop else clause
        lead = line[max(0, m.start() - 30):m.start()]
        n = _NUM.search(clause)
        if n is None or _RESULT.search(lead + clause) or _COUNTED.match(clause[n.end():]) or \
                re.search(r"\b(?:routers?|nodes?|vertices)\b[^.;]{0,12}$", lead, re.I):
            continue  # "six routers, A to F, and 9 links": names a range and a count, not a link
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if a == b:
            continue
        c = float(n.group(1)) if n.group(1) else float(spoken_number(n.group(2)) or 0)
        if not 0 < c <= MAX_COST:
            out.append(("!", f"Heard a cost of {n.group(0)} - a link costs more than 0 and at most {MAX_COST:g}",
                        m.group(0), m.start()))
            continue
        e[(min(a, b), max(a, b))] = c
        first = m.start() if first < 0 else first
        out.append(("~", None, n.group(0), m.end() + n.start()))  # that number is this link's cost
    if e != before:
        nodes = {x for k in e for x in k}
        if len(nodes) > MAX_NODES or len(e) > MAX_EDGES:
            out.append(("!", f"At most {MAX_NODES} nodes and {MAX_EDGES} links are drawn: that link is not",
                        line[max(first, 0):max(first, 0) + 12], max(first, 0)))
        else:
            out.append(("edges", edges_text(e), line[max(first, 0):max(first, 0) + 12], max(first, 0)))
    m = _FROM_TO.search(line)
    if m and _ROUTE.search(line) and not _COSTLY.search(line[max(0, m.start() - 30):m.start()]):
        out += [("source", m.group(1).upper(), m.group(0), m.start()), ("target", m.group(2).upper(), m.group(0), m.start())]
    else:
        m = _SOURCE.search(line)
        if m:
            out.append(("source", (m.group(1) or m.group(2) or m.group(3)).upper(), m.group(0), m.start()))
        m = _TARGET.search(line)
        if m:
            out.append(("target", (m.group(1) or m.group(2)).upper(), m.group(0), m.start()))
    for rx, msg in _NOT_DRAWN:
        mm = rx.search(line)
        if mm:
            out.append(("!", msg, mm.group(0), mm.start()))
    return out


TEMPLATE = Template(
    id="routing", name="Shortest-path routing", subject="networks",
    sim=RoutingSim, params=RoutingParams, slots=(), elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\bdijkstra\w*\b|\bshortest[- ](?:path|route)s?\b[^.;]{0,60}\b(?:graph|network|nodes?|routers?|"
                     r"links?|from (?-i:[A-H])\b)|\b(?:graph|network|routers?)\b[^.;]{0,60}\bshortest[- ](?:path|route)s?\b"
                     r"|\brouting (?:algorithms?|tables?)\b|\blink[- ]state routing\b|\bOSPF\b", re.IGNORECASE),
    lexicon=re.compile(r"\b(?:nodes?|routers?|links?|edges?|costs?|weights?|distances?|paths?|routes?|visit\w*|"
                       r"neighbou?rs?|packets?|dijkstra|shortest|table|source|destination|hops?)\b", re.IGNORECASE),
    guard=re.compile(r"\bneural networks?\b|\bsocial (?:networks?|media)\b|\bnetworking\b|\bneurons?\b|\bnerves?\b|"
                     r"\bfood (?:webs?|chains?)\b|\bblood\b|\bcapillar\w*\b|\b(?:light|ray|rays|beam)\b|\bfriends?\b|\bcareer path\b|\bpath of (?:light|the ball)"
                     r"|\bmetabolic pathways?\b|\btrade routes?\b", re.IGNORECASE),
    ordered=True,
    aliases=("routing", "dijkstra", "shortest path", "network", "graph", "router"),
    parse=parse, step_defs=step_defs,  # type: ignore[arg-type]
    listens=r"(?<![\w-])(?-i:[A-H])\s*(?:-|–|to|and)\s*(?-i:[A-H])(?![\w-])|\b(?:source|destination|bellman|distance vector)\b"
            r"|\b(?:visit|pick|choos|chose|select|take|took|explor|process|expand|finali[sz])\w*\s+(?-i:[A-H])(?![\w-])",
)
