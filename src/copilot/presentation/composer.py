"""Composer: content pieces → SlideSpec blocks, with a capacity model per layout (F-005). Pure functions.

Rules: existing items are never rebuilt (stable ids → the display animates only what is new); near-duplicates
are skipped; at most one `added` item per slide; what does not fit is returned as a leftover piece for a
continuation slide.
"""
from __future__ import annotations

import logging
import re
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Optional

from copilot.core.memory import titles_match
from copilot.presentation.content import Piece
from copilot.presentation.spec import (
    Block, CalloutBlock, CauseEffectBlock, CauseLink, Column, ComparisonBlock, DefinitionBlock, ExampleBlock,
    FormulaBlock, Item, Layout, PointsBlock, ProcessBlock, Row, SlideSpec, Step, TimelineBlock, TimelineEvent,
    Variable,
)

log = logging.getLogger(__name__)

CAPACITY = {"points": 6, "notes": 2, "def_points": 3, "steps": 6, "columns": 3, "rows": 5, "events": 6, "links": 4,
            "variables": 4, "secondary": 2}
LAYOUT_FOR = {"definition": "definition", "points": "key_points", "steps": "process_flow",
              "comparison": "comparison", "timeline": "timeline", "formula": "formula", "causes": "cause_effect",
              "example": "example"}
SECONDARY = ("example", "callout")
DUP_RATIO = 0.85
PROVISIONAL_PREFIX = "prov-"

TITLE_TEMPLATES = {  # facet keyword -> title; {t} = topic
    "definition": "What is {t}?", "meaning": "What is {t}?", "introduction": "{t}", "overview": "{t}",
    "process": "How {t} works", "how it works": "How {t} works", "mechanism": "How {t} works",
    "importance": "Why {t} matters", "significance": "Why {t} matters",
    "requirements": "What {t} needs", "needs": "What {t} needs",
}


# ---- text helpers ---------------------------------------------------------------------------------------
def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def is_duplicate(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long_ = sorted((na, nb), key=len)
    if len(short) >= 12 and short in long_:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= DUP_RATIO


def _new(existing: list[str], candidates: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for c in candidates:
        if not any(is_duplicate(c, e) for e in existing + out):
            out.append(c)
    return out


def cap(text: str) -> str:
    """Display case for a heading-like phrase: first letter upper, rest as said ("photosynthesis" -> "Photosynthesis")."""
    return text[:1].upper() + text[1:] if text else text


_JOINS = ("means", "is", "are", "refers", "stands")


def term_note(term: str, definition: str) -> str:
    """"photo" + "means light" -> "photo means light"; otherwise "Chlorophyll: green pigment"."""
    first = definition.split(" ", 1)[0].lower()
    return f"{term} {definition}" if first in _JOINS else f"{cap(term)}: {definition}"


def slide_title(topic: str, facet: str) -> str:
    if not facet or titles_match(facet, topic):
        return topic
    tpl = TITLE_TEMPLATES.get(facet.strip().lower())
    if tpl:
        t = topic if topic[:1].isupper() and topic[1:2].isupper() else topic.lower()  # keep acronyms
        title = tpl.format(t=t)
        return title[:1].upper() + title[1:]
    if _norm(topic) in _norm(facet):
        return facet
    return f"{facet} of {topic}"


def frame_slide(topic: str, facet: str, *, continuation_of: Optional[str] = None) -> SlideSpec:
    """An empty content slide for a frame (layout set by the first piece)."""
    has_facet = bool(facet) and not titles_match(facet, topic)
    return SlideSpec(title=slide_title(topic, facet), subtitle=topic, facet=facet if has_facet else None,
                     continuation_of=continuation_of, layout="concept", blocks=[])


def title_slide(topic: str, subtitle: str = "") -> SlideSpec:
    return SlideSpec(title=topic, subtitle=subtitle, layout="title", blocks=[])


# ---- slide inspection -----------------------------------------------------------------------------------
def _find(spec: SlideSpec, block_type: str):
    return next((b for b in spec.blocks if b.type == block_type), None)


def _replace_block(spec: SlideSpec, old, new) -> SlideSpec:
    return spec.model_copy(update={"blocks": [new if b is old else b for b in spec.blocks]})


def _add_block(spec: SlideSpec, block: Block, layout: Optional[Layout] = None) -> SlideSpec:
    upd: dict = {"blocks": [*spec.blocks, block]}
    if layout:
        upd["layout"] = layout
    return spec.model_copy(update=upd)


def teacher_items(spec: SlideSpec) -> int:
    """Displayed content units that are not provisional (0 → the slide can still be retitled/reshaped)."""
    n = 0
    for b in spec.blocks:
        if b.type == "points":
            n += sum(1 for i in b.items if not i.provisional)
        elif b.type == "definition":
            n += 1 + sum(1 for i in b.notes if not i.provisional)
        elif b.type == "process":
            n += len(b.steps)
        elif b.type == "comparison":
            n += max(1, len(b.rows))
        elif b.type == "timeline":
            n += len(b.events)
        elif b.type == "cause_effect":
            n += len(b.links)
        else:
            n += 1
    return n


def has_added(spec: SlideSpec) -> bool:
    for b in spec.blocks:
        items = b.items if b.type == "points" else b.notes if b.type == "definition" else []
        if any(i.added for i in items):
            return True
        if b.type in SECONDARY and b.id.startswith("added-"):
            return True
    return False


def _secondary_count(spec: SlideSpec) -> int:
    return sum(1 for b in spec.blocks if b.type in SECONDARY)


def _is_empty(spec: SlideSpec) -> bool:
    return teacher_items(spec) == 0 and not any(b.type not in ("points", "definition") for b in spec.blocks)


def describe(spec: SlideSpec, max_items: int = 6) -> str:
    """One-line summary of a slide for the interpretation prompt (CURRENT SLIDE)."""
    parts: list[str] = []
    room = ""
    for b in spec.blocks:
        if b.type == "points":
            parts += [i.text for i in b.items if not i.provisional]
            room = f"room for {max(0, CAPACITY['points'] - len(b.items))} more points"
        elif b.type == "definition":
            parts.append(f"{b.term}: {b.definition}")
            parts += [n.text for n in b.notes if not n.provisional]
        elif b.type == "process":
            parts += [f"{k + 1}. {s.label}" for k, s in enumerate(b.steps)]
            room = f"room for {max(0, CAPACITY['steps'] - len(b.steps))} more steps"
        elif b.type == "comparison":
            parts.append(" vs ".join(c.heading for c in b.columns) + f" ({len(b.rows)} rows)")
        elif b.type == "timeline":
            parts += [f"{e.when} {e.label}" for e in b.events]
        elif b.type == "cause_effect":
            parts += [f"{l.cause} -> {l.effect}" for l in b.links]
        elif b.type == "formula":
            parts.append(b.latex)
        elif b.type in SECONDARY:
            parts.append(f"{b.type}: {b.text}")
    body = "; ".join(parts[:max_items]) + ("; …" if len(parts) > max_items else "")
    layout = spec.layout.replace("_", " ")
    return f"{spec.title} ({layout})" + (f": {body}" if body else ": empty") + (f" [{room}]" if room else "")


# ---- merge ----------------------------------------------------------------------------------------------
def merge(spec: SlideSpec, piece: Piece, *, full: bool = False) -> tuple[SlideSpec, Optional[Piece]]:
    """Put a piece on a slide. Returns (new spec, leftover piece that needs another slide, or None).

    `full`: the display reported that this slide overflows; nothing more is added to it.
    """
    if piece.added and has_added(spec):
        log.info("dropping added piece (slide %s already has an added item): %s", spec.id, piece.all_text()[:2])
        return spec, None
    if full and not _is_empty(spec):
        return spec, piece
    if _is_empty(spec):  # nothing from the teacher yet (maybe a provisional item): the piece shapes the slide
        spec = spec.model_copy(update={"layout": LAYOUT_FOR[piece.kind], "blocks": []})
    fn = _MERGERS[piece.kind]
    return fn(spec, piece)


def _items(texts: list[str], added: bool) -> list[Item]:
    return [Item(text=t, added=added) for t in texts]


def _merge_points(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    pb = _find(spec, "points")
    db = _find(spec, "definition")
    if pb is not None:
        kept = [i for i in pb.items if not i.provisional]
        fresh = _new(_texts_on(spec), piece.texts)  # never against provisional teasers
        room = (CAPACITY["def_points"] if db is not None else CAPACITY["points"]) - len(kept)
        take, rest = fresh[:max(0, room)], fresh[max(0, room):]
        if piece.added:
            take, rest = take[:1], []
        new_items = kept + _items(take, piece.added) + [i for i in pb.items if i.provisional]
        spec = _replace_block(spec, pb, pb.model_copy(update={"items": new_items}))
        return spec, piece.with_texts(rest) if rest else None
    if db is not None:
        fresh = _new([db.definition] + [n.text for n in db.notes if not n.provisional], piece.texts)
        kept = [n for n in db.notes if not n.provisional]
        room = CAPACITY["notes"] - len(kept)
        take, rest = fresh[:max(0, room)], fresh[max(0, room):]
        if piece.added:
            take, rest = take[:1], []
        notes = kept + _items(take, piece.added) + [n for n in db.notes if n.provisional]
        spec = _replace_block(spec, db, db.model_copy(update={"notes": notes}))
        if rest:  # notes are full: a short supporting list under the definition
            spec = _add_block(spec, PointsBlock(items=[]))
            return _merge_points(spec, piece.with_texts(rest))
        return spec, None
    if not spec.blocks:
        texts = list(piece.texts[:1]) if piece.added else list(piece.texts)
        take, rest = texts[:CAPACITY["points"]], texts[CAPACITY["points"]:]
        spec = _add_block(spec, PointsBlock(items=_items(take, piece.added)), "key_points")
        return spec, piece.with_texts(rest) if rest else None
    if len(piece.texts) == 1 and _secondary_count(spec) < CAPACITY["secondary"]:
        if any(is_duplicate(piece.texts[0], t) for t in _texts_on(spec)):
            return spec, None
        block = CalloutBlock(kind="note", text=piece.texts[0])
        if piece.added:
            block = block.model_copy(update={"id": "added-" + block.id})
        return _add_block(spec, block), None
    return spec, piece


def _texts_on(spec: SlideSpec) -> list[str]:
    out: list[str] = []
    for b in spec.blocks:
        if b.type == "points":
            out += [i.text for i in b.items if not i.provisional]
        elif b.type == "definition":
            out += [b.term, b.definition] + [n.text for n in b.notes if not n.provisional]
        elif b.type in SECONDARY:
            out.append(b.text)
        elif b.type == "process":
            out += [s.label for s in b.steps]
    return out


def _merge_definition(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    db = _find(spec, "definition")
    if db is None and not spec.blocks:
        return _add_block(spec, DefinitionBlock(term=cap(piece.term), definition=piece.definition), "definition"), None
    if db is not None:
        if titles_match(db.term, piece.term):
            if is_duplicate(db.definition, piece.definition):
                return spec, None
            note = piece.definition
        else:
            note = term_note(piece.term, piece.definition)
        return _merge_points(spec, Piece("points", lines=piece.lines, added=piece.added, texts=(note,)))
    if _find(spec, "points") is not None:
        return _merge_points(spec, Piece("points", lines=piece.lines, added=piece.added,
                                         texts=(term_note(piece.term, piece.definition),)))
    return spec, piece


def _merge_steps(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    pb = _find(spec, "process")
    if pb is None:
        if spec.blocks:
            return spec, piece
        pb = ProcessBlock()
        spec = _add_block(spec, pb, "process_flow")
    fresh = _new([s.label for s in pb.steps], piece.texts)
    room = CAPACITY["steps"] - len(pb.steps)
    take, rest = fresh[:max(0, room)], fresh[max(0, room):]
    spec = _replace_block(spec, pb, pb.model_copy(update={"steps": pb.steps + [Step(label=t) for t in take]}))
    return spec, piece.with_texts(rest) if rest else None


def _merge_comparison(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    cb = _find(spec, "comparison")
    if cb is None:
        if spec.blocks:
            return spec, piece
        cols = list(piece.columns) or ["", ""]
        width = max(len(cols), max((len(c) for _, c in piece.rows), default=0))
        cols = (cols + [""] * width)[:min(width, CAPACITY["columns"])]
        cb = ComparisonBlock(columns=[Column(heading=cap(h)) for h in cols])
        spec = _add_block(spec, cb, "comparison")
    elif piece.columns and not _same_columns([c.heading for c in cb.columns], list(piece.columns)):
        return spec, piece
    n = len(cb.columns)
    existing = [r.aspect + " " + " ".join(r.cells) for r in cb.rows]
    rows = []
    for aspect, cells in piece.rows:
        text = aspect + " " + " ".join(cells)
        if any(is_duplicate(text, e) for e in existing):
            continue
        existing.append(text)
        rows.append(Row(aspect=cap(aspect), cells=(list(cells) + [""] * n)[:n]))
    room = CAPACITY["rows"] - len(cb.rows)
    take, rest = rows[:max(0, room)], rows[max(0, room):]
    spec = _replace_block(spec, cb, cb.model_copy(update={"rows": cb.rows + take}))
    if rest:
        return spec, replace(piece, rows=tuple((r.aspect, tuple(r.cells)) for r in rest),
                             columns=tuple(c.heading for c in cb.columns))
    return spec, None


def _same_columns(a: list[str], b: list[str]) -> bool:
    a = [x for x in a if x]
    b = [x for x in b if x]
    return not a or not b or (len(a) >= len(b) and all(any(titles_match(x, y) for y in a) for x in b))


def _merge_pairs(block_type: str, layout: Layout, cap_key: str):
    def merge_fn(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
        blk = _find(spec, block_type)
        if blk is None:
            if spec.blocks:
                return spec, piece
            blk = TimelineBlock() if block_type == "timeline" else CauseEffectBlock()
            spec = _add_block(spec, blk, layout)
        if block_type == "timeline":
            existing = [f"{e.when} {e.label}" for e in blk.events]
            make = lambda a, b: TimelineEvent(when=a, label=b)  # noqa: E731
            current = blk.events
        else:
            existing = [f"{l.cause} {l.effect}" for l in blk.links]
            make = lambda a, b: CauseLink(cause=a, effect=b)  # noqa: E731
            current = blk.links
        fresh = []
        for a, b in piece.pairs:
            if not any(is_duplicate(f"{a} {b}", e) for e in existing):
                existing.append(f"{a} {b}")
                fresh.append((a, b))
        room = CAPACITY[cap_key] - len(current)
        take, rest = fresh[:max(0, room)], fresh[max(0, room):]
        field = "events" if block_type == "timeline" else "links"
        spec = _replace_block(spec, blk, blk.model_copy(update={field: current + [make(a, b) for a, b in take]}))
        return spec, replace(piece, pairs=tuple(rest)) if rest else None
    return merge_fn


def _merge_formula(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    fb = _find(spec, "formula")
    f = piece.formula
    assert f is not None
    if fb is not None and is_duplicate(fb.latex, f.expression):
        return spec, None
    if spec.blocks:
        return spec, piece
    variables = [Variable(symbol=s, meaning=m) for s, m in f.variables[:CAPACITY["variables"]]]
    return _add_block(spec, FormulaBlock(latex=f.expression, spoken=f.expression, variables=variables), "formula"), None


def _merge_example(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    text = piece.texts[0]
    if any(is_duplicate(text, t) for t in _texts_on(spec)):
        return spec, None
    if not spec.blocks:
        return _add_block(spec, ExampleBlock(text=text), "example"), None
    if _secondary_count(spec) < CAPACITY["secondary"]:
        block = ExampleBlock(text=text)
        if piece.added:
            block = block.model_copy(update={"id": "added-" + block.id})
        return _add_block(spec, block), None
    if _find(spec, "points") is not None:
        return _merge_points(spec, Piece("points", lines=piece.lines, added=piece.added, texts=(f"e.g. {text}",)))
    return spec, piece


_MERGERS = {
    "points": _merge_points, "definition": _merge_definition, "steps": _merge_steps,
    "comparison": _merge_comparison, "timeline": _merge_pairs("timeline", "timeline", "events"),
    "causes": _merge_pairs("cause_effect", "cause_effect", "links"), "formula": _merge_formula,
    "example": _merge_example,
}


# ---- provisional fast path ------------------------------------------------------------------------------
def set_provisional(spec: SlideSpec, text: str) -> Optional[SlideSpec]:
    """Show (or update in place) one provisional item on a list-like slide. None if the slide has no place."""
    pid = PROVISIONAL_PREFIX + spec.id
    pb = _find(spec, "points")
    if pb is not None:
        if sum(1 for i in pb.items if not i.provisional) >= CAPACITY["points"]:
            return None
        items = [i for i in pb.items if not i.provisional] + [Item(id=pid, text=text, provisional=True)]
        return _replace_block(spec, pb, pb.model_copy(update={"items": items}))
    db = _find(spec, "definition")
    if db is not None:
        if sum(1 for n in db.notes if not n.provisional) >= CAPACITY["notes"]:
            return None
        notes = [n for n in db.notes if not n.provisional] + [Item(id=pid, text=text, provisional=True)]
        return _replace_block(spec, db, db.model_copy(update={"notes": notes}))
    return None


def clear_provisional(spec: SlideSpec) -> SlideSpec:
    blocks = []
    changed = False
    for b in spec.blocks:
        if b.type == "points" and any(i.provisional for i in b.items):
            b = b.model_copy(update={"items": [i for i in b.items if not i.provisional]})
            changed = True
        elif b.type == "definition" and any(n.provisional for n in b.notes):
            b = b.model_copy(update={"notes": [n for n in b.notes if not n.provisional]})
            changed = True
        blocks.append(b)
    return spec.model_copy(update={"blocks": blocks}) if changed else spec
