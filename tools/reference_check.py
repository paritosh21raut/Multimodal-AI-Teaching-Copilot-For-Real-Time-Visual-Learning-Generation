"""F-012 dry check (0 LLM tokens): recorded lecture units + study material → which units would get a REFERENCE
passage (and how many prompt tokens it costs), which image requests the teacher's figures would answer, and the
speech terms. Real MiniLM; the files are indexed into a temporary library (data/notes is not touched).
    .venv/Scripts/python tools/reference_check.py SESSION [SESSION ...] --files a.pdf b.pdf [--clip] [-v]
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
import prompt_ab  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from copilot.core.events import decode_event as _decode  # noqa: E402


def decode_event(kind: str, payload: str):
    """Sessions recorded before a command was removed (e.g. "freeze", round 4 step C) hold events that no longer
    decode; they do not matter for the prompts."""
    try:
        return _decode(kind, payload)
    except ValidationError:
        return None


prompt_ab.decode_event = decode_event
rebuild = prompt_ab.rebuild
from copilot.notes.library import NotesLibrary  # noqa: E402
from copilot.notes.reference import ReferenceIndex, load_vocab  # noqa: E402
from copilot.understanding import prompt as P  # noqa: E402
from copilot.understanding.embedder import MiniLmEmbedder  # noqa: E402
from copilot.understanding.interpreter import InterpreterSettings  # noqa: E402


def image_queries(session: str) -> list[tuple[str, str]]:
    db = sqlite3.connect(ROOT / "data" / "sessions" / session / "session.sqlite")
    out = []
    for kind, payload in db.execute("select type, payload from events where type='ImageRequested' order by seq"):
        ev = decode_event(kind, payload)
        if ev is not None and (ev.query, ev.kind) not in out:
            out.append((ev.query, ev.kind))
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--clip", action="store_true", help="also run the CLIP gate on matched figures")
    ap.add_argument("-v", action="store_true", help="print every passage")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="refcheck-"))
    try:
        emb = MiniLmEmbedder(ROOT / "models" / "minilm")
        emb.load()
        lib = NotesLibrary(tmp / "notes")
        ref = ReferenceIndex(lib, emb, load_vocab(ROOT / "models" / "minilm" / "tokenizer.json"))
        for f in a.files:
            doc = lib.add(Path(f).read_bytes(), Path(f).name)
            ref.build(doc)
            print(f"indexed {doc.name}: {doc.pages} pages, {ref.chunk_count(doc)} passages, "
                  f"{len(ref._load(doc).figures)} figures")
        print(f"speech terms: {', '.join(ref.terms())}")
        s = InterpreterSettings()
        finder = None
        if a.clip:
            from copilot.visuals.cache import ImageCache
            from copilot.visuals.clip import ClipScorer
            from copilot.visuals.finder import ImageFinder

            clip = ClipScorer(ROOT / "models" / "clip")
            clip.load()
            finder = ImageFinder(ImageCache(tmp / "cache"), clip)
        for session in a.sessions:
            units = await rebuild(session)
            hits, extra = [], 0
            for u in units:
                query = " ".join([*(l.text for l in u.lines), " ".join(u.state.slide_context.split()[:40])])
                sn = ref.snippet(query)
                plain = P.build_prompt(u.state, u.lines, dynamic_budget=s.dynamic_budget_tokens,
                                       total_budget=s.prompt_budget_tokens)
                if sn is None:
                    continue
                with_ref = P.build_prompt(u.state, u.lines, dynamic_budget=s.dynamic_budget_tokens,
                                          total_budget=s.prompt_budget_tokens, reference=(sn.cite, sn.text))
                extra += with_ref.tokens - plain.tokens
                hits.append((u.index, sn, with_ref.tokens - plain.tokens, with_ref.reference != ""))
            print(f"\n{session}: {len(units)} units, {len(hits)} with a passage, +{extra} prompt tokens in all "
                  f"({extra / max(1, len(units)):.0f} per unit on average)")
            for i, sn, d, used in hits:
                said = " ".join(units[i].lines[0].text.split()[:12]) if units[i].lines else ""
                print(f"  unit {i:3d} {sn.score:.2f} {sn.cite:<34} +{d:3d} tok{'' if used else ' (no room)'} | {said}")
                if a.v:
                    print(f"           {sn.text[:300]}")
            print("  image requests answered by the study material (label match):")
            for q, kind in image_queries(session):
                m = ref.figures(q)
                if not m:
                    continue
                gate = ""
                if finder is not None:
                    from PIL import Image
                    (sim, margin), = finder._score(q, kind, [(None, Image.open(m[0].path).convert("RGB"))])
                    ok = sim >= finder.s.min_similarity and margin >= finder.s.min_margin
                    gate = f" clip {sim:.3f} {margin:+.3f} -> {'USED' if ok else 'web'}"
                print(f"    {q!r} ({kind}) -> {m[0].doc.name} p.{m[0].figure.page} label {m[0].score:.2f}{gate}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
