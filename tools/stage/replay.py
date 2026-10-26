"""Replay stage op scripts (E2): each line's ops -> the event log (validator) -> the graph -> one stage.patch per line.

    .venv/Scripts/python tools/stage/replay.py                 # all fixtures: patches + the E2 gate sheets
    .venv/Scripts/python tools/stage/replay.py push rain       # some, patches only (artifacts/stage/replay/)
    .venv/Scripts/python tools/stage/replay.py --check         # the expected key facts of every fixture

An op script (tests/fixtures/stage/ops/<name>.jsonl): a header {name, about, ref (an E1 reference patch or null),
expect [...]} then one object per teacher line {id, say, ops [...], src?}. Deterministic: no clock, no LLM, 0 tokens.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from copilot.stage import timeline  # noqa: E402
from copilot.stage.log import EventLog  # noqa: E402

OPS = ROOT / "tests" / "fixtures" / "stage" / "ops"
REF = ROOT / "tests" / "fixtures" / "stage" / "patches"
OUT = ROOT / "artifacts" / "stage" / "replay"
ORDER = ["push", "throw", "moonmars", "rain", "car", "carry", "desk", "seesaw", "swing", "tug", "dog", "lift"]


def load(name: str) -> tuple[dict, list[dict]]:
    rows = [json.loads(s) for s in (OPS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    return rows[0], rows[1:]


def replay(name: str) -> tuple[dict, EventLog, list[dict]]:
    head, lines = load(name)
    log, patches, prev = EventLog(), [], None
    for i, ln in enumerate(lines):
        log.say(ln["id"], ln["say"])
        log.delta(ln["ops"], ln["id"], ln.get("src", "llm"), t_ms=1000 * (i + 1))
        p = timeline.build(log.fold(), prev, rev=i + 1)
        p["name"], p["caption"] = name, ln["say"]
        patches.append(p)
        prev = p
    return head, log, patches


def _close(a: Any, b: Any, tol: float = 1e-3) -> bool:
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str):
        return a == b
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def check(head: dict, log: EventLog, patches: list[dict]) -> list[str]:
    """The fixture's expected key facts; returns the failures (empty: all hold)."""
    bad = []
    for x in head["expect"]:
        if "rejects" in x:
            n = len(log.rejects())
            if n != x["rejects"]:
                bad.append(f"rejects {n} != {x['rejects']}: {[e.reason for e in log.rejects()]}")
            continue
        p = patches[x["at"]]
        tag = f"patch {x['at']}"
        if "fact" in x:
            law, k, v = x["fact"]
            got = p["laws"].get(law, {}).get("facts", {}).get(k)
            if not _close(v, got):
                bad.append(f"{tag}: {law}.{k} = {got!r}, expected {v!r}")
        elif "num" in x:
            pid, src, v = x["num"]
            rec = p["numbers"].get(pid)
            if not rec or rec["src"] != src or not _close(v, rec["v"]):
                bad.append(f"{tag}: number {pid} = {rec}, expected {src} {v}")
        elif "num_symbol" in x:
            if x["num_symbol"] in p["numbers"]:
                bad.append(f"{tag}: {x['num_symbol']} is printed ({p['numbers'][x['num_symbol']]}), expected a symbol")
        elif "event" in x:
            law, ev = x["event"]
            if ev not in p["laws"].get(law, {}).get("events", {}):
                bad.append(f"{tag}: no event {law}.{ev}")
        elif "badge" in x:
            if x["badge"] not in p["badges"]:
                bad.append(f"{tag}: no badge {x['badge']!r} ({p['badges']})")
        elif "no_badge" in x:
            if x["no_badge"] in p["badges"]:
                bad.append(f"{tag}: badge {x['no_badge']!r} should be gone")
        elif "clip" in x:
            who, clip = x["clip"]
            if not any(t["id"] == who and t["kind"] == "clip" and t["clip"] == clip for t in p["tracks"]):
                bad.append(f"{tag}: {who} plays no {clip}")
        elif "view" in x:
            if p["view"] != x["view"]:
                bad.append(f"{tag}: view {p['view']} != {x['view']}")
        elif "overlay" in x:
            if not any(o["kind"] == x["overlay"] for o in p["overlays"]):
                bad.append(f"{tag}: no {x['overlay']} overlay")
        elif "draw" in x:
            i, d = x["draw"]
            if not any(e["id"] == i and e["draw"] == d for e in p["entities"]):
                bad.append(f"{tag}: {i} is not drawn as {d}")
        elif "backdrop" in x:
            if (p.get("backdrop") or {}).get("id") != x["backdrop"]:
                bad.append(f"{tag}: backdrop {p.get('backdrop')} != {x['backdrop']}")
        elif "path_dx" in x:
            i, sign = x["path_dx"]
            s = next(t for t in p["tracks"] if t["id"] == i and t["kind"] == "path")["samples"]
            dx = s[-1][1] - s[0][1]
            if (dx > 1e-6) - (dx < -1e-6) != sign:
                bad.append(f"{tag}: {i} moves {dx:+.3f} m, expected sign {sign}")
        elif "same_speed" in x:
            a, b = x["same_speed"]
            sp = []
            for i in (a, b):
                s = next(t for t in p["tracks"] if t["id"] == i and t["kind"] == "path")["samples"]
                sp.append((s[-1][1] - s[0][1]) / (s[-1][0] - s[0][0]))
            if not _close(sp[0], sp[1]):
                bad.append(f"{tag}: speeds {sp}")
        elif "socket_ends" in x:
            i, ev = x["socket_ends"]
            sk = next(t for t in p["tracks"] if t["id"] == i and t["kind"] == "socket")
            evt = [e["t"] for t in p["tracks"] if t["kind"] == "clip" for e in t.get("events", []) if e["name"] == ev]
            if not evt or not _close(sk.get("t1"), evt[0]):
                bad.append(f"{tag}: {i}'s socket ends at {sk.get('t1')}, the {ev} event is at {evt}")
        else:
            bad.append(f"unknown check {x}")
    return bad


def write(name: str, patches: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(patches):
        (OUT / f"{name}_{i + 1}.json").write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def sheets(results: dict[str, tuple[dict, list[dict]]]) -> None:
    """The E2 gate: each fixture's last patch at its 3 key frames, beside the E1 reference (mid key frame)."""
    sys.path.insert(0, str(ROOT / "tools" / "stage"))
    import shoot

    def job(names, out, title):
        def run(s):
            cells = []
            for n in names:
                head, patches = results[n]
                p = patches[-1]
                for t in p["keyframes"]:
                    cells.append((f"{n}  t = {t:.2f} s  (E2, from ops)", s.patch(p, t)))
                if head.get("ref") and (REF / f"{head['ref']}.json").exists():
                    rp = json.loads((REF / f"{head['ref']}.json").read_text(encoding="utf-8"))
                    t = rp["keyframes"][len(rp["keyframes"]) // 2]
                    cells.append((f"{head['ref']}  t = {t:.2f} s  (E1 hand-made)", s.patch(rp, t)))
                else:
                    cells.append(("(no E1 reference)", s.shot("() => stageDev.show({rev: 1, backdrop: 'outdoor', entities: [], frame: {cx: 0, cy: 2, s: 200}}, 0)")))
            shoot.sheet(cells, title, out, 4, (480, 300))
        return run

    half = len(ORDER) // 2
    shoot.run([job(ORDER[:half], shoot.OUT / "sheet_e2_a.png", "E2: fixtures 1-6 from op scripts (3 key frames) | E1 reference"),
               job(ORDER[half:], shoot.OUT / "sheet_e2_b.png", "E2: fixtures 7-12 from op scripts (3 key frames) | E1 reference")])


def main(argv: list[str]) -> None:
    only_check = "--check" in argv
    names = [a for a in argv if not a.startswith("--")] or ORDER
    results, failed = {}, 0
    for n in names:
        head, log, patches = replay(n)
        bad = check(head, log, patches)
        failed += bool(bad)
        rj = log.rejects()
        print(f"{n:9s} {len(patches)} patches, {len(log.events)} events, {len(rj)} rejected"
              + ("" if not bad else "\n  FAIL " + "\n  FAIL ".join(bad)))
        for e in rj:
            print(f"          reject: {e.op.get('op')} {e.reason}")
        results[n] = (head, patches)
        if not only_check:
            write(n, patches)
    if not only_check and names == ORDER:
        sheets(results)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
