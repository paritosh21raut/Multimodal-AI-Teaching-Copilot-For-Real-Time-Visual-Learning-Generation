"""TEMPORARY (paper validation, docs/paper/VALIDATION.md): record one evaluation test into verify_results/<name>/.

    .venv/Scripts/python tools/eval_test.py run [--name test7] [--source mic|web] [--note "..."] [-- <copilot args>]
    .venv/Scripts/python tools/eval_test.py export <name> [<session_id>]     # (re)build the folder from data/sessions
    .venv/Scripts/python tools/eval_test.py list

`run` starts `python -m copilot` exactly as usual (Enter to start, q + Enter to end; the control and display pages
open as always), copies everything the terminal shows into terminal_log.txt, and when the app ends exports the test:

    verify_results/<name>/
        terminal_log.txt     everything the app printed (INIT, QUOTA, LIVE, ENDED summary, warnings)
        meta.json            name, source, note, session id, date, minutes, subject, slide count, copilot args
        transcript.txt       the transcript as heard (one line per final segment)
        slides/NN.png        every final slide, rendered by the real display at 1920x1080 in the lecture's theme
        slides.md            the same slides as text (title, layout, items) for review sheets
        session/             session.sqlite (full event log) + lecture.json (final deck), the source of all results

Names: the user's own / other people's tests are test1, test2, ...; internet lecture recordings run by Claude are
web1, web2, ... (--source web, normally with `-- --audio-file <wav> --no-wait`). Zero LLM tokens beyond the lecture
itself; export alone uses none.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verify_results"
SESSIONS = ROOT / "data" / "sessions"
PY = ROOT / ".venv" / "Scripts" / "python.exe"


def next_name(prefix: str) -> str:
    used = {int(m.group(1)) for p in OUT.glob(f"{prefix}*") if (m := re.fullmatch(prefix + r"(\d+)", p.name))}
    return f"{prefix}{max(used, default=0) + 1}"


def run(name: str, source: str, note: str, copilot_args: list[str]) -> int:
    folder = OUT / name
    if folder.exists() and any(folder.iterdir()):
        raise SystemExit(f"{folder} already exists; pick another --name")
    folder.mkdir(parents=True, exist_ok=True)
    print(f"[TEST]  {name}: recording into {folder.relative_to(ROOT)}", flush=True)
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    session = None
    log_path = folder / "terminal_log.txt"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"> python -m copilot {' '.join(copilot_args)}\n")
        # stdin stays the console, so Enter / q + Enter reach the app as usual
        proc = subprocess.Popen([str(PY), "-m", "copilot", *copilot_args], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        try:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
                log.flush()
                m = re.search(r"\[READY\] session (\S+)", line)
                if m:
                    session = m.group(1)
            code = proc.wait()
        except KeyboardInterrupt:  # Ctrl+C reaches the app too; let it end and write its summary
            for line in proc.stdout:
                sys.stdout.write(line)
                log.write(line)
            code = proc.wait()
    if session is None:
        print(f"[TEST]  no session started; only the terminal log is kept in {folder}", flush=True)
        return code
    export(name, session, source=source, note=note, copilot_args=copilot_args)
    return code


def transcript_lines(db: Path) -> list[str]:
    rows = sqlite3.connect(db).execute("select payload from events where type='TranscriptFinal' order by seq")
    out = []
    for (payload,) in rows:
        seg = json.loads(payload)["segment"]
        out.append(f"[{seg['start']:7.1f}] {' '.join(seg['text'].split())}")
    return out


def deck_from_log(db: Path) -> list[dict]:
    """The final deck when no lecture.json was written: last SlidePatch per slide, in the last DeckState order."""
    con = sqlite3.connect(db)
    specs = {}
    for (payload,) in con.execute("select payload from events where type='SlidePatch' order by seq"):
        p = json.loads(payload)
        specs[p["slide_id"]] = p["spec"]
    row = con.execute("select payload from events where type='DeckState' order by seq desc limit 1").fetchone()
    order = json.loads(row[0])["slide_ids"] if row else list(specs)
    return [specs[i] for i in order if i in specs]


def last_end(db: Path) -> float:
    row = sqlite3.connect(db).execute(
        "select payload from events where type='TranscriptFinal' order by seq desc limit 1").fetchone()
    return json.loads(row[0])["segment"]["end"] if row else 0.0


def theme_from_log(db: Path) -> str:
    row = sqlite3.connect(db).execute(
        "select payload from events where type='ThemeChanged' order by seq desc limit 1").fetchone()
    return json.loads(row[0])["theme"] if row else "light"


def _tree(node: dict, depth: int) -> list[str]:
    return [f"{'  ' * depth}- {node.get('label', '')}"] + [x for c in node.get("children", []) for x in _tree(c, depth + 1)]


def block_text(b: dict) -> list[str]:
    t = b.get("type")
    items = lambda xs: [f"  - {i['text']}" for i in xs if not i.get("provisional")]  # noqa: E731
    if t == "definition":
        return [f"- **{b.get('term', '')}**: {b.get('definition', '')}"] + items(b.get("notes", []))
    if t == "points":
        return ([f"- *{b['heading']}*"] if b.get("heading") else []) + [x[2:] for x in items(b.get("items", []))]
    if t == "image":
        return [f"- [image] {b.get('alt', '')} ({b.get('licence', '')})"]
    if t == "formula":
        return [f"- [formula] {b.get('latex', '')}"] + [f"  - {v}" for v in b.get("variables", [])]
    if t == "example":
        return [f"- [example] {b.get('title', '')} {b.get('text', '')}".replace("  ", " ")]
    if t == "callout":
        return [f"- [{b.get('kind', 'note')}] {b.get('text', '')}"]
    if t == "process":
        return [f"- [process{', cyclic' if b.get('cyclic') else ''}]"] + [
            f"  {n}. {s['label']}" + (f" — {s['detail']}" if s.get("detail") else "") for n, s in enumerate(b["steps"], 1)]
    if t == "comparison":
        cols = [c["heading"] for c in b.get("columns", [])]
        return [f"- [comparison] {' vs '.join(cols)}"] + [
            f"  - {r['aspect']}: " + " | ".join(r["cells"]) for r in b.get("rows", [])]
    if t == "facts":
        return ([f"- *{b['heading']}*"] if b.get("heading") else []) + [
            f"- {f['label']}: {f['value']}" for f in b.get("facts", [])]
    if t == "hierarchy":
        return ["- [hierarchy]"] + _tree(b["root"], 1)
    if t == "groups":
        return ([f"- *{b['heading']}*"] if b.get("heading") else []) + [
            x for g in b.get("groups", []) for x in [f"- {g['label']}"] + items(g.get("items", []))]
    if t == "cause_effect":
        return [f"- {link['cause']} → {link['effect']}" for link in b.get("links", [])]
    if t == "timeline":
        return [f"- {e['when']}: {e['label']}" + (f" — {e['detail']}" if e.get("detail") else "") for e in b["events"]]
    texts = [v for k, v in b.items() if k not in ("type", "id") and isinstance(v, str) and v]
    return [f"- [{t}] " + " / ".join(texts)]


async def render(slides: list[dict], theme: str, out_dir: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from display_harness import browser_page, display_harness, wait_for_slide
    from copilot.core.events import Command, CommandReceived
    from copilot.presentation.spec import SlideSpec

    async with display_harness(theme) as h:
        async with browser_page(f"{h.url}/display") as page:
            for i, raw in enumerate(slides, 1):
                spec = SlideSpec.model_validate(raw)
                await h.deck.add(spec, activate=False)
                await h.bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": spec.id})))
                await h.settle()
                await wait_for_slide(page, spec.id)
                await asyncio.sleep(0.8)  # images load from the local cache
                await page.screenshot(path=str(out_dir / f"{i:02d}.png"))
            if page.errors:
                print("[TEST]  display console errors:", page.errors, flush=True)


def export(name: str, session: str, source: str = "", note: str = "", copilot_args: list[str] | None = None) -> None:
    folder = OUT / name
    src = SESSIONS / session
    if not (src / "session.sqlite").exists():
        raise SystemExit(f"no session {session} in {SESSIONS}")
    meta_path = folder / "meta.json"
    old = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    (folder / "session").mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src / "session.sqlite") as live, sqlite3.connect(folder / "session" / "session.sqlite") as copy:
        live.backup(copy)  # includes rows still in the -wal file (a plain file copy can miss them)
    if (src / "lecture.json").exists():
        shutil.copy2(src / "lecture.json", folder / "session" / "lecture.json")
    lines = transcript_lines(src / "session.sqlite")
    (folder / "transcript.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    record = {}
    if (src / "lecture.json").exists():
        record = json.loads((src / "lecture.json").read_text(encoding="utf-8")).get("record", {})
    slides = record.get("slides") or deck_from_log(src / "session.sqlite")
    theme = record.get("theme") or theme_from_log(src / "session.sqlite")
    md = [f"# {name} — {record.get('title', '')}", "", f"Session {session}, {len(slides)} slides.", ""]
    for i, s in enumerate(slides, 1):
        part = f" (part {s['part']})" if s.get("part") else ""
        md += [f"## Slide {i:02d}: {s.get('title', '')}{part}", f"*{s.get('layout', '')}*"
               + (f" · {s['subtitle']}" if s.get("subtitle") else ""), ""]
        for b in s.get("blocks", []):
            md += block_text(b)
        md.append("")
    (folder / "slides.md").write_text("\n".join(md), encoding="utf-8")

    shots = folder / "slides"
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir()
    if slides:
        asyncio.run(render(slides, theme, shots))

    meta = {
        "name": name,
        "source": source or old.get("source", ""),
        "note": note or old.get("note", ""),
        "session_id": session,
        "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(record.get("started", time.time()))),
        "title": record.get("title", ""),
        "minutes": round(record.get("minutes") or last_end(src / "session.sqlite") / 60, 1),
        "utterances": len(lines),
        "slides": len(slides),
        "theme": theme,
        "simulated": record.get("simulated", False),
        "copilot_args": copilot_args if copilot_args is not None else old.get("copilot_args", []),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[TEST]  {name}: session {session}, {meta['minutes']} min, {len(slides)} slides -> "
          f"{folder.relative_to(ROOT)} (slides/, slides.md, transcript.txt, session/)", flush=True)


def list_tests() -> None:
    def key(p: Path):
        m = re.fullmatch(r"([a-z]+)(\d+)", p.name)
        return (m.group(1), int(m.group(2))) if m else (p.name, 0)

    rows = sorted((p for p in OUT.iterdir() if (p / "meta.json").exists()), key=key)
    if not rows:
        print("no tests yet")
    for p in rows:
        m = json.loads((p / "meta.json").read_text(encoding="utf-8"))
        print(f"{m['name']:8} {m['source']:4} {m['date']}  {m['minutes']:5.1f} min  {m['slides']:3} slides  "
              f"{m['title'][:40]:40}  {m['note'][:40]}")


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # a redirected stdout is cp1252 on Windows; the app prints any Unicode
    argv = sys.argv[1:]
    copilot_args = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[:argv.index("--")] if "--" in argv else argv
    p = argparse.ArgumentParser(prog="eval_test")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--name")
    r.add_argument("--source", choices=["mic", "web"], default="mic")
    r.add_argument("--note", default="")
    e = sub.add_parser("export")
    e.add_argument("name")
    e.add_argument("session", nargs="?")
    sub.add_parser("list")
    a = p.parse_args(argv)
    OUT.mkdir(exist_ok=True)
    if a.cmd == "run":
        name = a.name or next_name("web" if a.source == "web" else "test")
        sys.exit(run(name, a.source, a.note, copilot_args))
    if a.cmd == "export":
        session = a.session or json.loads((OUT / a.name / "meta.json").read_text(encoding="utf-8"))["session_id"]
        export(a.name, session)
    else:
        list_tests()


if __name__ == "__main__":
    main()
