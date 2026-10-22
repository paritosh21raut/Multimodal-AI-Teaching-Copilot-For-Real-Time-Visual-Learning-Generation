"""TCP: three-way handshake, sliding window, a lost segment and its retransmission (F-014 S4). Renderer:
web/sims/tcp.js.

A sender and a receiver on two time lines (time runs down), as in the textbook figure. The schedule is worked out
here as a deterministic discrete-event run (Solution.events, one SimEvent per arrow), the stage plays it in time:

    handshake   SYN (0 → 1), SYN-ACK (1 → 2), ACK (2 → 3); data from t = 3 (time in one-way delays D)
    sender      up to W segments in flight, one every GAP; one timer on the oldest unacknowledged segment
                (TCP, Go-Back-N), one per segment (Selective Repeat); timeout RTO after its send
    receiver    TCP: keeps segments out of order, cumulative ACK = the next segment it expects
                Go-Back-N: drops segments out of order, ACK = the next it expects (duplicate ACKs)
                Selective Repeat: keeps them, ACKs each one ("ACK 3" = segment 3 arrived)
    loss        the segment said lost is lost the first time it is sent, its retransmission arrives
    timeout     TCP: the oldest unacknowledged segment again; Go-Back-N: it and every one after it already sent;
                Selective Repeat: that segment only
    fast        (TCP, when said) the third duplicate ACK resends the oldest unacknowledged segment at once

    W 4, 8 segments, segment 3 lost, TCP, RTO 3: 1, 2 arrive (ACK 2, ACK 3); 3 lost; 4, 5, 6 arrive (ACK 3 x 3,
    duplicates); 3 times out and is sent again; it arrives, ACK 7 (4, 5, 6 were kept); 7, 8 follow

Truthfulness: segment numbers are names, not values; the window, the number of segments and the lost one print only
when said; the counts in the readout (segments sent, resent, the time in RTTs) only when the window and the number of
segments were said. Congestion control, flow control and closing the connection are notices (user 2026-10-20).
"""
from __future__ import annotations

import heapq
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, SimEvent, SimLabel, Slot, Solution, Template, _Model, fmt, known,
)
from copilot.simulation.values import spoken_number

D = 1.0          # one-way delay (the time unit)
GAP = 0.5        # between two segments sent back to back
RTO = 3.0        # retransmission timeout (a little more than one RTT = 2 D)
HANDSHAKE = 3.0  # data starts after SYN, SYN-ACK, ACK
STAGE_PER_D = 1.1  # stage seconds per D
SLOTS = (
    Slot("window", "Window (segments)", "W", "", 1, 8, 1, 4, "count"),  # read by parse only (not "4000 bytes")
    Slot("segments", "Segments to send", "N", "", 1, 12, 1, 8, "count"),
    Slot("lost", "Lost segment (0 = none)", "lost", "", 0, 12, 1, 0, "count", absent=True),
)
ELEMENTS = (
    Element("handshake", "Three-way handshake"), Element("data", "Segments"), Element("acks", "ACKs"),
    Element("window", "Sliding window"), Element("timers", "Timeouts"), Element("readout", "Values"),
)
PROTOCOLS = {"tcp": "TCP", "gbn": "Go-Back-N", "sr": "Selective Repeat"}


class TcpParams(_Model):
    window: float = Field(default=4, ge=1, le=8)
    segments: float = Field(default=8, ge=1, le=12)
    lost: float = Field(default=0, ge=0, le=12)
    protocol: Literal["tcp", "gbn", "sr"] = "tcp"
    fast: Literal["off", "on"] = "off"


class TcpSim(SimBase):
    template: Literal["tcp"] = "tcp"
    params: TcpParams = Field(default_factory=TcpParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("w", "n", "lost", "protocol", "note", "assume")


def schedule(w: int, n: int, lost: int, protocol: str, fast: bool) -> tuple[list[SimEvent], float]:
    """The run: its events (seg / ack / timeout / fast / base / syn / synack / hsack) and when the last ACK arrives.
    One link: a segment leaves only when the link is free (one every GAP), resends first; nothing is booked ahead, so
    a timeout resends only segments that have left (S4 review b)."""
    ev: list[SimEvent] = [SimEvent(kind="syn", t=0.0, t2=D, label="SYN"),
                          SimEvent(kind="synack", t=D, t2=2 * D, label="SYN-ACK"),
                          SimEvent(kind="hsack", t=2 * D, t2=3 * D, label="ACK")]
    q: list[tuple[float, int, str, int, int]] = []  # (time, order, what, seq / ack, timer generation)
    order = 0

    def push(t: float, what: str, x: int, gen: int = 0) -> None:
        nonlocal order
        order += 1
        heapq.heappush(q, (round(t, 9), order, what, x, gen))

    base, nxt, line_free, gen = 1, 1, HANDSHAKE, {0: 0}
    sent_once: set[int] = set()
    acked: set[int] = set()                  # Selective Repeat
    buf: set[int] = set()                    # the receiver's (TCP, SR)
    resend: list[int] = []                   # waiting for the link
    expected, dup = 1, 0
    sends = resends = 0
    free_at = -1.0                           # a "free" event is pending for this time

    def send(seq: int, t: float, again: bool) -> None:
        nonlocal line_free, sends, resends
        line_free = t + GAP
        first = seq not in sent_once
        sent_once.add(seq)
        drop = first and seq == lost
        ev.append(SimEvent(kind="seg", t=t, t2=t + D, n=seq, lost=drop, label=f"{seq}" + (" again" if again else "")))
        sends += 1
        resends += 1 if again else 0
        if not drop:
            push(t + D, "arrive", seq)
        if protocol == "sr":
            timer(seq, t)
        elif seq == base:
            timer(0, t)

    def timer(key: int, t: float) -> None:  # (re)start a timer: TCP / GBN key 0, SR the segment
        gen[key] = gen.get(key, 0) + 1
        push(t + RTO, "timeout", key, gen[key])

    def kick(t: float) -> None:
        """Send what may go now (resends first, then new segments in the window); else wait for the link."""
        nonlocal nxt, free_at
        while True:
            want = bool(resend) or (nxt <= n and nxt < base + w)
            if not want:
                return
            if line_free > t + 1e-9:
                if free_at != line_free:
                    free_at = line_free
                    push(line_free, "free", 0)
                return
            if resend:
                send(resend.pop(0), t, True)
            else:
                send(nxt, t, False)
                nxt += 1

    ev.append(SimEvent(kind="base", t=HANDSHAKE, n=1))
    kick(HANDSHAKE)
    t_end = HANDSHAKE
    while q:
        t, _, what, x, g = heapq.heappop(q)
        if base > n:
            break
        if what == "free":
            kick(t)
        elif what == "arrive":  # at the receiver: its ACK
            if protocol == "gbn":
                if x == expected:
                    expected += 1
                a = expected
            elif protocol == "tcp":
                buf.add(x)
                while expected in buf:
                    expected += 1
                a = expected
            else:
                a = x
            ev.append(SimEvent(kind="ack", t=t, t2=t + D, n=a, label=f"ACK {a}"))
            push(t + D, "ack", a)
        elif what == "ack":
            t_end = t
            if protocol == "sr":
                acked.add(x)
                gen[x] = gen.get(x, 0) + 1  # its timer stops
                if x in resend:
                    resend.remove(x)
                moved = False
                while base in acked:
                    base, moved = base + 1, True
                if moved:
                    ev.append(SimEvent(kind="base", t=t, n=base))
                kick(t)
            elif x > base:
                base, dup = x, 0
                resend[:] = [r for r in resend if r >= base]
                ev.append(SimEvent(kind="base", t=t, n=base))
                if base < nxt:
                    timer(0, t)
                else:
                    gen[0] += 1  # nothing outstanding: the timer stops
                kick(t)
            elif x == base:
                dup += 1
                if protocol == "tcp" and fast and dup == 3 and base not in resend:
                    ev.append(SimEvent(kind="fast", t=t, n=base, label="3 duplicate ACKs"))
                    resend.insert(0, base)
                    kick(t)
        elif what == "timeout" and g == gen.get(x, 0):
            if protocol == "sr":
                if x in acked or x in resend:
                    continue
                ev.append(SimEvent(kind="timeout", t=t, n=x, label="timeout"))
                resend.append(x)
            else:
                if base >= nxt:
                    continue
                ev.append(SimEvent(kind="timeout", t=t, n=base, label="timeout"))
                dup = 0  # Reno: the duplicate count starts again after a timeout
                resend[:] = list(range(base, nxt)) if protocol == "gbn" else [base]
            kick(t)
    ev.append(SimEvent(kind="done", t=t_end, n=sends, b=str(resends)))
    return ev, t_end


def solve(p: TcpParams, src: dict[str, str]) -> Solution:
    said = lambda name: src.get(name, "default") in ("said", "teacher", "computed")  # noqa: E731
    w, n = int(p.window), int(p.segments)
    past = int(p.lost) > n and said("lost")  # "segment 10 is lost" with 8 segments: no such segment
    lost = int(p.lost) if int(p.lost) <= n else 0
    fast = p.fast == "on" and p.protocol == "tcp"
    events, t_end = schedule(w, n, lost, p.protocol, fast)
    labels = {
        "w": SimLabel(symbol="W", text=f"{w} segments", source=src["window"]) if said("window")  # type: ignore[arg-type]
        else SimLabel(symbol="W"),
        "n": SimLabel(symbol="N", text=str(n), source=src["segments"]) if said("segments")  # type: ignore[arg-type]
        else SimLabel(symbol="N"),
        "lost": SimLabel(symbol="lost", text=f"segment {lost}", source=src["lost"]) if lost and said("lost")  # type: ignore[arg-type]
        else SimLabel(symbol=""),
        "protocol": SimLabel(symbol=(PROTOCOLS[p.protocol] if said("protocol") else "TCP" if fast else "")
                             + (", fast retransmit" if fast else "")),
        "note": SimLabel(symbol=f"no segment {int(p.lost)}: {n} are sent" if past else ""),
        # the run's timing is the model's, not the teacher's: said on the stage whenever a time is printed
        "assume": SimLabel(symbol=""),
    }
    derived: list[Derived] = []
    if said("window") and said("segments") and known(src, {s.name: s for s in SLOTS}, "lost") and not past:
        labels["assume"] = SimLabel(symbol=f"assumed: a segment every {fmt(GAP / (2 * D))} RTT, "
                                           f"timeout {fmt(RTO / (2 * D))} RTT")
        done = next(e for e in events if e.kind == "done")
        derived += [Derived(id="sent", label="Segments sent", symbol="sent", value=float(done.n), text=str(done.n)),
                    Derived(id="resent", label="Sent again", symbol="again", value=float(done.b), text=done.b),
                    Derived(id="rtts", label="Time (from the first SYN)", symbol="time", value=t_end / (2 * D),
                            text=f"{fmt(t_end / (2 * D))} RTT")]
    drive = {"t_end": t_end, "stage_per_d": STAGE_PER_D, "hold_s": 2.5, "n": float(n), "w": float(w),
             "still_t": t_end * STAGE_PER_D}  # stage seconds: the whole run drawn
    return Solution(drive=drive, labels=labels, derived=derived, events=events)


def default_shown(p: TcpParams, src: dict[str, str]) -> list[str]:
    return ["handshake", "data", "acks", "window", "timers", "readout"]


# ---- speech: window, number of segments, the lost one, the protocol, fast retransmit, notices -----------------------
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
        "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
        "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10, "11th": 11, "12th": 12}
_NUMW = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_SEG = r"(?:segments?|packets?|frames?)"
_LOSS = r"(?:is|gets|got|was) (?:lost|dropped)|(?:is|gets|got|was) not (?:received|delivered)|never arrives|goes missing"
_ACK_LOST = re.compile(rf"\b(?:ACK|acknowledg\w*)s?\s+(?:for|of|number)?\s*(?:(?:the\s+)?(?:{'|'.join(_ORD)})\s+)?"
                       rf"(?:{_SEG}\s+)?(?:{_NUMW})?\s*(?:{_LOSS})", re.IGNORECASE)
_TWO_LOST = re.compile(rf"\b{_SEG}\s+(?:{_NUMW})\s+and\s+(?:{_NUMW})\s+(?:are|were|get|got)\s+(?:lost|dropped)", re.I)
_ZERO = re.compile(rf"\b{_SEG}\s+(?:number\s+)?(?:0|zero)\b[^.;]{{0,20}}?\b(?:{_LOSS})", re.IGNORECASE)
_LOST = re.compile(rf"\b{_SEG}\s+(?:number\s+)?(?P<a>{_NUMW})\b[^.;]{{0,20}}?\b(?:{_LOSS})|"
                   rf"\bthe (?P<o>{'|'.join(_ORD)})(?: {_SEG}| one)?\b[^.;]{{0,20}}?\b(?:{_LOSS})|"
                   rf"\b(?:lose|drop|loses|drops|lost|dropped)\s+(?:the\s+)?(?:(?P<o2>{'|'.join(_ORD)})\s+{_SEG}|"
                   rf"{_SEG}\s+(?:number\s+)?(?P<a2>{_NUMW}))\b", re.IGNORECASE)
_WINDOW = re.compile(rf"(?<!receiver's )(?<!receiver )(?<!advertised )\bwindow(?: size)?(?: of(?: size)?| is| =| equal to| as)?"
                     rf"\s+(?P<a>{_NUMW})\b(?!\s*(?:bytes?|kb|kilobytes?|mss|bits?)\b)|"
                     rf"\b(?:go[- ]?back[- ]?n|gbn)\b[^.;]{{0,15}}\bN\s?(?:=|is|equals)\s?(?P<d>{_NUMW})\b|"
                     rf"\b(?P<b>{_NUMW})[- ]segment window\b|\bwindow of (?P<c>{_NUMW}) {_SEG}", re.IGNORECASE)
_COUNT = re.compile(rf"\b(?:sends?|sending|transmits?|transfer|has|have|send out)\s+(?:a total of\s+)?(?P<a>{_NUMW})\s+"
                    rf"(?:data\s+)?{_SEG}\b|\b(?P<b>{_NUMW})\s+(?:data\s+)?{_SEG}\s+(?:to send|in total|altogether|"
                    rf"(?:are|will be|get) (?:sent|transmitted))\b",
                    re.IGNORECASE)
_NO_LOSS = re.compile(rf"\bno (?:{_SEG}|loss|losses)\b(?: (?:is|are) lost)?|\bnothing is lost\b|\bwithout (?:any )?loss\b",
                      re.IGNORECASE)
_PROTO = ((re.compile(r"\bgo[- ]?back[- ]?n\b|\bgo back n\b", re.I), "gbn"),
          (re.compile(r"\bselective[- ]repeat\b|\bselective (?:retransmission|reject)\b", re.I), "sr"))
_FAST = re.compile(r"\bfast retransmi\w*\b|\b(?:three|3|triple) duplicate (?:acks?|acknowledg\w*)\b", re.I)
_STOP_WAIT = re.compile(r"\bstop[- ]and[- ]wait\b", re.I)
_NOT_DRAWN = (
    (re.compile(r"\bcongestion (?:control|window|avoidance)\b|\bslow start\b|\bcwnd\b|\bAIMD\b|\bTCP (?:Reno|Tahoe|Cubic)\b",
                re.I), "Congestion control is not drawn: the window stays the size said"),
    (re.compile(r"\bflow control\b|\breceiver'?s? window\b|\brwnd\b|\badvertised window\b", re.I),
     "Flow control is not drawn: the window stays the size said"),
    (re.compile(r"\bFIN\b|\bconnection (?:termination|teardown|release)\b|\bclos(?:e|ing) the connection\b|"
                r"\bfour[- ]way handshake\b", re.I), "Closing the connection (FIN) is not drawn"),
)


def _n(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    v = spoken_number(s)
    return int(v) if v is not None and v == int(v) else None


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    out: list[tuple[str, Any, str, int]] = []
    m = _WINDOW.search(line)
    if m and (v := _n(m.group("a") or m.group("b") or m.group("c") or m.group("d"))) is not None:
        out.append(("window", float(v), m.group(0), m.start()))
    elif (m := _STOP_WAIT.search(line)) is not None:
        out.append(("window", 1.0, m.group(0), m.start()))
    m = _COUNT.search(line)
    if m and (v := _n(m.group("a") or m.group("b"))) is not None:
        out.append(("segments", float(v), m.group(0), m.start()))
    m = _LOST.search(line)
    if (a := _ACK_LOST.search(line)) is not None:
        out.append(("!", "A lost ACK is not drawn: the simulation loses one data segment", a.group(0), a.start()))
        m = None
    elif (z := _ZERO.search(line)) is not None:
        out.append(("!", "Segments are numbered from 1 here: say which one, counting from 1", z.group(0), z.start()))
        m = None
    elif (two := _TWO_LOST.search(line)) is not None:
        out.append(("!", "One lost segment is drawn: say which one", two.group(0), two.start()))
        m = None
    if m:
        v = _ORD.get((m.group("o") or m.group("o2") or "").lower()) or _n(m.group("a") or m.group("a2"))
        if v is not None:
            out.append(("lost", float(v), m.group(0), m.start()))
    elif (m := _NO_LOSS.search(line)) is not None:
        out.append(("lost", 0.0, m.group(0), m.start()))
    for rx, proto in _PROTO:
        if (m := rx.search(line)) is not None:
            out.append(("protocol", proto, m.group(0), m.start()))
            break
    if (m := _FAST.search(line)) is not None:
        out.append(("fast", "on", m.group(0), m.start()))
    for rx, msg in _NOT_DRAWN:
        if (m := rx.search(line)) is not None:
            out.append(("!", msg, m.group(0), m.start()))
    for h in items:  # times, sizes in bytes: not this simulation's values
        if h.start >= 0:
            out.append(("~", None, h.said, h.start))
    return out


TEMPLATE = Template(
    id="tcp", name="TCP: handshake, window, retransmission", subject="networks",
    sim=TcpSim, params=TcpParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    # S4 review b: "TCP segment header", "over a TCP connection" are not the run; "how the ACK works in TCP" is
    setup=re.compile(r"\bthree[- ]way handshake\b|\bTCP\b[^.;]{0,60}\b(?:handshake|sliding window|retransmi\w*|"
                     r"acknowledg\w*|ACKs?|lost (?:segments?|packets?)|sends? (?:data|segments?))\b|\b(?:handshake|"
                     r"sliding window|retransmi\w*|acknowledg\w*|ACKs?)\b[^.;]{0,60}\bTCP\b|\bsliding window protocols?\b|\bgo[- ]?back[- ]?n\b|"
                     r"\bselective[- ]repeat\b|\bstop[- ]and[- ]wait (?:protocol|ARQ)\b|\bARQ\b", re.IGNORECASE),
    lexicon=re.compile(r"\b(?:TCP|SYN|ACKs?|acknowledg\w*|segments?|packets?|window|sender|receiver|timeout|timer|"
                       r"retransmi\w*|lost|dropped|duplicate|handshake|sequence|go[- ]back[- ]n|selective)\b",
                       re.IGNORECASE),
    guard=re.compile(r"\bshak\w* hands?\b|\bhandshake (?:deal|agreement|ceremony)\b|\bsliding window (?:technique|"
                     r"problems?|maximum|minimum|sum|of size|on an? array)\b|\barrays?\b|\bsubarrays?\b|"
                     r"\bsliding (?:windows? )?(?:doors?|glass|frames?)\b|\bwindow (?:panes?|sills?|frames?)\b|"
                     r"\b(?:headers?|formats?|fields?)\b",
                     re.IGNORECASE),
    aliases=("tcp", "handshake", "sliding window", "retransmission", "go-back-n", "selective repeat", "ack", "network"),
    parse=parse,
    listens=r"\b(?:lost|dropped|go[- ]?back[- ]?n|selective repeat|fast retransmi\w*|duplicate acks?|stop[- ]and[- ]wait|"
            r"congestion|slow start|flow control|FIN)\b",
)
