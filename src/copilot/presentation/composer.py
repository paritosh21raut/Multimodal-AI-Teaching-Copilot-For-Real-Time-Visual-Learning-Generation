"""Composer: content pieces → SlideSpec blocks (F-005). Pure functions.

Space, not slot counts, decides what fits: every block has an estimated height in design pixels (the 1920×1080
stage, mirroring web/shared/slide.css), and a piece goes on the slide while the body stays within its budget.
Related content therefore stays together (a definition, its classification tree and a few fact tiles on one
slide); what does not fit is returned as a leftover for the next part of the same frame.

Rules: existing items are never rebuilt (stable ids → the display animates only what is new); near-duplicates
are skipped; at most one `added` item per slide; at most one large diagram (process, comparison, timeline,
cause-effect, formula, tree) per slide.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Callable, Optional

from copilot.core.events import new_id
from copilot.core.memory import title_key, titles_match
from copilot.presentation.content import Piece, drop_self_alias
from copilot.presentation.mathtext import has_fraction, to_latex, visible_length
from copilot.presentation.spec import (
    Block, CalloutBlock, CauseEffectBlock, CauseLink, Column, ComparisonBlock, DefinitionBlock, ExampleBlock, Fact,
    FactsBlock, FormulaBlock, Group, GroupsBlock, HierarchyBlock, ImageBlock, Item, PointsBlock, ProcessBlock, Row,
    SlideSpec, Step, TimelineBlock, TimelineEvent, TreeNode, Variable,
)

log = logging.getLogger(__name__)

# Hard caps per block (readability), on top of the space budget.
CAPACITY = {"points": 8, "notes": 2, "steps": 10, "columns": 3, "rows": 6, "events": 6, "links": 4,
            "variables": 4, "secondary": 2, "facts": 8, "groups": 4, "group_items": 8, "tree": 6, "definitions": 6,
            "member_points": 3, "formulas": 4}
BODY_BUDGET_PX = 740       # slide body height at the default type size (auto-fit can still shrink to 0.8); measured
                           # 754-763 px in Edge on 29 slides of the live test 2026-10-06 (700 left lonely last parts)
BODY_WIDTH_PX = 1696
MAIN_WIDTH_ASIDE_PX = 1040  # main column when an aside (example/callout) is shown
BLOCK_GAP_PX = 32
IMAGE_GAP_PX = 56           # image layout (F-007b): content column | image column (mirrors slide.css .with-image)
IMAGE_HEIGHT_PX = BODY_BUDGET_PX  # image column sizing (mirrors slide.js imageColumn)
IMAGE_TOP_MAX_PX = 380      # an image beside the text above a formula (slide.css .image-top) is at most this tall
MEMBER_GAP_PX = 36          # member cards / concept columns (slide.css .def-pair)
LAYOUT_FOR = {"definition": "definition", "points": "key_points", "steps": "process_flow",
              "comparison": "comparison", "timeline": "timeline", "formula": "formula", "causes": "cause_effect",
              "example": "example", "facts": "facts", "groups": "groups", "tree": "hierarchy"}
BLOCK_LAYOUT = {"definition": "definition", "points": "key_points", "process": "process_flow",
                "comparison": "comparison", "timeline": "timeline", "formula": "formula",
                "cause_effect": "cause_effect", "example": "example", "callout": "concept", "facts": "facts",
                "groups": "groups", "hierarchy": "hierarchy", "image": "concept"}
LARGE = {"process", "comparison", "timeline", "cause_effect", "formula", "hierarchy"}
FULL_WIDTH = LARGE | {"facts", "groups"}  # mirrors FULL_WIDTH_PRIMARY in slide.js: no aside next to these
SECONDARY = ("example", "callout")
DUP_RATIO = 0.85
PROVISIONAL_PREFIX = "prov-"

TITLE_TEMPLATES = {  # facet keyword -> title; {t} = topic, {is}/{s} agree with a plural topic ("What are lenses?")
    "definition": "What {is} {t}?", "meaning": "What {is} {t}?", "introduction": "{t}", "overview": "{t}",
    "process": "How {t} work{s}", "how it works": "How {t} work{s}", "mechanism": "How {t} work{s}",
    "importance": "Why {t} matter{s}", "significance": "Why {t} matter{s}",
    "requirements": "What {t} need{s}", "needs": "What {t} need{s}",
}
DEFINITION_FACETS = ("definition", "meaning")
_SINGULAR_ENDINGS = ("ss", "is", "us", "as", "ics", "ous", "sis")


def is_plural(phrase: str) -> bool:
    """"Human body systems", "lenses" → True; "photosynthesis", "physics", "gas", "Theory of gases" → False (cheap
    English rule on the head noun: the word before "of")."""
    words = re.split(r"\s+of\s+", phrase.strip(), maxsplit=1, flags=re.IGNORECASE)[0].split()
    last = words[-1].lower() if words else ""
    return len(last) > 3 and last.endswith("s") and not last.endswith(_SINGULAR_ENDINGS)


def what_is(term: str) -> str:
    return f"What {'are' if is_plural(term) else 'is'} {_lower_term(term)}?"


# ---- text helpers ---------------------------------------------------------------------------------------
def _norm(text: str) -> str:
    # "+" and "#" are part of names: "C++" and "C#" are not "C" (live test 2026-10-06 dropped C++ as a duplicate)
    return " ".join(re.findall(r"[a-z0-9]+[+#]*", text.lower()))


def is_duplicate(a: str, b: str) -> bool:
    """Same item in other words. Containment counts only for whole words ("organic chemistry" is NOT inside
    "inorganic chemistry")."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long_ = sorted((na, nb), key=len)
    # containment = the same item with a few words more; a bare term inside a longer sentence ("acceleration" in
    # "Unit of acceleration: m/s²") is a new item that mentions it (V1a: such points were silently dropped)
    if len(short) >= 12 and 2 * len(short) >= len(long_) and f" {short} " in f" {long_} ":
        return True
    # similar wording is a duplicate only with the same content words: "Plants take in oxygen" vs "Plants give
    # out oxygen", or "fact 1" vs "fact 2", are different items
    if _content_words(na) != _content_words(nb):
        return False
    return SequenceMatcher(None, na, nb).ratio() >= DUP_RATIO


_STOP = {"the", "a", "an", "of", "and", "in", "to", "for", "is", "are", "it", "its", "on", "by", "with", "as",
         "be", "that", "this", "which", "from", "at", "or"}


def _content_words(norm: str) -> frozenset[str]:
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in norm.split() if w not in _STOP)


def _subsumed(new: str, old: str) -> bool:
    """A new item that only repeats words of an existing one ("Formed by end-to-end overlap of orbitals" after
    "Formed by end-to-end overlap of half-filled orbitals with opposite spin", long test 2026-10-06)."""
    cn, co = _content_words(_norm(new)), _content_words(_norm(old))
    return len(cn) >= 3 and cn < co


def _new(existing: list[str], candidates: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for c in candidates:
        if not any(is_duplicate(c, e) or _subsumed(c, e) for e in existing + out):
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


def _lower_term(term: str) -> str:
    """A term inside a sentence: a term said in sentence case loses its first capital ("Dipole moment" → "dipole
    moment"); a Title Case term stays as said, since names cannot be told from words ("French Revolution", "Boyle's
    Law"; long test 2026-10-06: "What is boyle's Law?", "What is french Revolution?"); acronyms stay ("DNA")."""
    words = term.split()
    if not words or words[0][1:2].isupper() or any(w[:1].isupper() for w in words[1:]) or "'" in words[0] \
            or "’" in words[0]:
        return term
    return words[0][:1].lower() + words[0][1:] + term[len(words[0]):]


def term_key(text: str) -> frozenset[str]:
    """Words of a concept's name; hyphenated words stay whole ("non-polar" is not "polar"), plurals folded."""
    words = re.findall(r"[a-z0-9]+(?:[-'’][a-z0-9]+)*", text.lower())
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
                     for w in words if w not in _TERM_FILLER)


_TERM_FILLER = {"the", "a", "an", "of", "and", "in", "to", "for", "its", "their", "how", "what"}  # = memory._FILLER


def same_term(a: str, b: str) -> bool:
    """The same concept named again ("Ionic Bond" / "ionic bonds", "KE" / "Kinetic energy"). A qualified term is
    another concept: "Resonance hybrid" is not "Resonance", "Bond dissociation enthalpy" not "Bond enthalpy" (long
    test 2026-10-06: these became points under the shorter term and lost their names)."""
    ka, kb = term_key(a), term_key(b)
    if ka and ka == kb:
        return True
    for x, y in ((a, b), (b, a)):
        compact = re.sub(r"[^A-Za-z]", "", x)
        if 2 <= len(compact) <= 4 and compact.isupper() and compact == _initials(y):
            return True
    return False


def _is_part_term(term: str, of: str) -> bool:
    """A word part explained inside a definition ("photo" of "photosynthesis") — a note, not a new concept."""
    t, o = _norm(term), _norm(of)
    return bool(t) and t != o and len(t) < len(o) and (o.startswith(t) or o.endswith(t)) and " " not in t


def slide_title(topic: str, facet: str) -> str:
    if not facet or titles_match(facet, topic):
        return topic
    tpl = TITLE_TEMPLATES.get(facet.strip().lower())
    if tpl:
        t = _lower_term(topic)  # keep acronyms and names ("DNA", "Boyle's law")
        plural = is_plural(t)
        return cap(tpl.format(t=t, **{"is": "are" if plural else "is", "s": "" if plural else "s"}))
    return facet  # the crumb already shows the topic ("CHEMISTRY — MATTER"); "Matter of Chemistry" reads badly


def frame_slide(topic: str, facet: str, *, continuation_of: Optional[str] = None) -> SlideSpec:
    """An empty content slide for a frame (layout set by the first piece)."""
    has_facet = bool(facet) and not titles_match(facet, topic)
    return SlideSpec(title=slide_title(topic, facet), subtitle=topic, facet=facet if has_facet else None,
                     continuation_of=continuation_of, layout="concept", blocks=[])


def title_slide(topic: str, subtitle: str = "") -> SlideSpec:
    return SlideSpec(title=topic, subtitle=subtitle, layout="title", blocks=[])


def process_rows(n: int) -> list[range]:
    """Step indices per row (mirrors slide.js processRows): up to 6 steps in one row; 7-10 in two rows, the longer
    first (round 5, user 2026-10-06: a whole digestive process on one slide, not split 6 + 4 across parts)."""
    if n <= 6:
        return [range(n)] if n else []
    k = math.ceil(n / 2)
    return [range(k), range(k, n)]


def continue_numbering(prev: SlideSpec, nxt: SlideSpec) -> SlideSpec:
    """The next part of a process keeps counting its steps (Step 11, 12 …; live test 2026-10-06 restarted at 1)."""
    a, b = _find(prev, "process"), _find(nxt, "process")
    if a is None or b is None or b.start > 1:
        return nxt
    return _replace_block(nxt, b, b.model_copy(update={"start": a.start + len(a.steps)}))


# ---- height model ---------------------------------------------------------------------------------------
def _lines(text: str, chars_per_line: float) -> int:
    return max(1, math.ceil(len(text) / max(8.0, chars_per_line)))


def _cpl(width_px: float, font_px: float) -> float:
    return width_px / (font_px * 0.5)  # average glyph ≈ 0.5 em for Segoe UI


def image_column_px(aspect: float) -> float:
    """Width of the image column (mirrors slide.js imageColumn): wider for landscape images, and a tall image takes
    only the width it needs at the body height, so the content keeps the rest."""
    widest = 720.0 if aspect >= 1.25 else 600.0
    return float(round(min(widest, max(380.0, IMAGE_HEIGHT_PX * aspect))))


def image_of(spec: SlideSpec) -> Optional[ImageBlock]:
    return next((b for b in spec.blocks if b.type == "image"), None)


def content_width(spec: SlideSpec) -> float:
    img = image_of(spec)
    return BODY_WIDTH_PX - image_column_px(img.aspect) - IMAGE_GAP_PX if img is not None else BODY_WIDTH_PX


def block_height(b: Block, width: float = BODY_WIDTH_PX, narrow: bool = False) -> float:
    """Estimated rendered height (design px at the default type size). narrow: beside an image (facts in 2 columns)."""
    if b.type == "definition":
        h = 92 + 57 * _lines(b.definition, _cpl(width - 116, 42))  # card + its "Definition" tab (slide.css)
        if b.notes:
            h += 30 + 64 * math.ceil(sum(len(n.text) + 6 for n in b.notes) / _cpl(width, 26))
        return h
    if b.type == "points":
        items = [i.text for i in b.items]
        h = 44 if b.heading else 0
        if not items:
            return h
        two = width >= BODY_WIDTH_PX - 1 and len(items) > 3 and all(len(t) < 90 for t in items)
        if two:
            cpl = _cpl((width - 28) / 2 - 138, 34)
            rows = [max(_lines(a, cpl), _lines(c, cpl)) for a, c in zip(items[::2], items[1::2] + [""])]
            return h + sum(52 + 45 * r for r in rows) + 22 * (len(rows) - 1)
        cpl = _cpl(width - 138, 34)
        return h + sum(52 + 45 * _lines(t, cpl) for t in items) + 20 * (len(items) - 1)
    if b.type == "facts":
        n = len(b.facts)
        per_row = 2 if narrow else 4 if n != 3 and all(len(f.value) <= 24 for f in b.facts) else 3
        tile = (width - 24 * (per_row - 1)) / per_row - 68
        rows = [b.facts[i:i + per_row] for i in range(0, n, per_row)]
        heights = [max(56 + 33 * _lines(f.label, _cpl(tile, 26)) + 48 * _lines(f.value or "x", _cpl(tile, 42))
                       for f in row) for row in rows]
        return (44 if b.heading else 0) + sum(heights) + 24 * max(0, len(rows) - 1)
    if b.type == "groups":
        if not b.groups:
            return 0
        width_each = (width - 28 * (len(b.groups) - 1)) / len(b.groups)
        tallest = max(math.ceil(sum(len(i.text) + 4 for i in g.items) / _cpl(width_each - 60, 30)) for g in b.groups)
        return (44 if b.heading else 0) + 110 + 46 * tallest
    if b.type == "hierarchy":
        if narrow and any(c.children for c in b.root.children):
            # beside an image a tree of several levels is a card per divided kind (slide.js), stacked
            cards = [c for c in b.root.children if c.children]
            leaves = [c for c in b.root.children if not c.children]
            return (44 + sum(110 + 46 * math.ceil(sum(len(k.label) + 4 for k in c.children) / _cpl(width - 60, 30))
                             for c in cards) + 22 * len(cards)
                    + (46 * math.ceil(sum(len(k.label) + 4 for k in leaves) / _cpl(width, 30)) if leaves else 0))
        if narrow:  # beside an image the classification is one card: its label, then the kinds as chips
            chips = math.ceil(sum(len(c.label) + 4 for c in b.root.children) / _cpl(width - 60, 30))
            return 110 + 46 * max(1, chips)
        return 110 + 120 * (tree_depth(b.root) - 1)
    if b.type == "process":
        longest = max((len(s.label) for s in b.steps), default=10)
        rows = process_rows(len(b.steps))
        per_row = max(len(r) for r in rows) if rows else 1
        gap = 40 if per_row >= 5 else 56
        per = (width - gap * max(0, per_row - 1)) / per_row
        if per_row >= 5:  # narrow cards: smaller label (slide.css .process-row.many)
            card = 104 + 34 * _lines("x" * longest, _cpl(per - 44, 26))
        else:
            card = 120 + 41 * _lines("x" * longest, _cpl(per - 56, 34))
        return len(rows) * card + 70 * (len(rows) - 1) + (44 if b.start > 1 else 0)
    if b.type == "comparison":
        return 80 + sum(44 + 45 * max(_lines(c, _cpl(width / (len(r.cells) + 1), 34)) for c in r.cells or [""])
                        for r in b.rows)
    if b.type == "timeline":
        return 280
    if b.type == "cause_effect":
        return len(b.links) * 120
    if b.type == "formula":
        shown = visible_length(b.latex) if b.latex else len(b.spoken)
        return (140 + 72 * _lines("x" * shown, _cpl(width - 128, 55)) + (50 if has_fraction(b.latex) else 0)
                + (60 if b.variables else 0))
    if b.type in SECONDARY:
        return 110 + 45 * _lines(b.text, _cpl(width - 80, 34))
    if b.type == "image":
        col = image_column_px(b.aspect)
        return min(BODY_BUDGET_PX, col / max(0.2, b.aspect))
    return 120


def _split(blocks: list, members: bool = False) -> tuple[list, list]:
    """(main, aside) exactly as slide.js splitBlocks lays them out. With an image (image layout) everything else is
    the content column and the image is alone in its column. Member cards take the full width (no aside)."""
    if any(b.type == "image" for b in blocks):
        return [b for b in blocks if b.type != "image"], [b for b in blocks if b.type == "image"][:1]
    if len(blocks) < 2 or members or any(b.type in FULL_WIDTH for b in blocks) \
            or sum(1 for b in blocks if b.type == "definition") > 1:
        return blocks, []
    main = [blocks[0]] + [b for b in blocks[1:] if b.type not in SECONDARY + ("image",)]
    aside = [b for b in blocks[1:] if b.type in SECONDARY + ("image",)]
    return main, aside


def grid_columns(n: int) -> int:
    """Member cards per row (mirrors slide.js): 1 | 2 | 3 | 2×2 | 3 + 2 | 3×2."""
    return 1 if n <= 1 else 3 if n == 3 or n >= 5 else 2


def _member_height(d: DefinitionBlock, width: float, cols: int) -> float:
    """A member card (slide.css .def-pair): the term as its heading, then the meaning card at body size."""
    term_px = 42 if cols >= 3 else 48.3
    # 12: measured in Edge (long test 2026-10-06 cards: 180 / 227 / 309 px for rows of 1 / 2 / 3; 20 was 7-9 px over)
    h = 12 + term_px * 1.1 * _lines(d.term, _cpl(width, term_px * 1.1))
    h += 68 + 46 * _lines(d.definition, _cpl(width - 92, 34))
    if d.notes:
        h += 20 + 50 * math.ceil(sum(len(n.text) + 6 for n in d.notes) / _cpl(width, 26))
    return h


def image_top(blocks: list) -> bool:
    """Image layout with a formula (mirrors slide.js): the text above the formula sits beside the image, the formula
    and what follows it take the full width below (live test 2026-10-06: the photosynthesis intro had no image)."""
    if not any(b.type == "image" for b in blocks):
        return False
    rest = [b for b in blocks if b.type != "image"]
    at = next((i for i, b in enumerate(rest) if b.type == "formula"), None)
    return at is not None and at > 0


FORMULA_SET_EQ_PX = 106    # one compact equation card of a formula set (slide.css .formula-set .formula-eq)
FORMULA_SET_GAP_PX = 22


def _formula_set_height(fs: list[FormulaBlock], width: float) -> float:
    """Several formulas said together (mirrors slide.js FormulaSet): stacked compact cards, one shared legend."""
    h = 0.0
    for f in fs:
        shown = visible_length(f.latex) if f.latex else len(f.spoken)
        h += FORMULA_SET_EQ_PX + 69 * (_lines("x" * shown, _cpl(width - 112, 49)) - 1) \
            + (44 if has_fraction(f.latex) else 0)
    h += FORMULA_SET_GAP_PX * (len(fs) - 1)
    seen: dict[str, str] = {}
    for f in fs:
        for v in f.variables:
            seen.setdefault(v.symbol, v.meaning)
    if seen:
        h += 34 + 46 * math.ceil(sum(len(s) + len(m) + 8 for s, m in seen.items()) / _cpl(width, 26))
    return h


def _stack_height(blocks: list[Block], width: float, narrow: bool = False) -> float:
    """Blocks stacked in one column; consecutive slide-wide formulas count as one formula set."""
    parts: list[float] = []
    run: list[FormulaBlock] = []
    for b in blocks + [None]:
        if b is not None and b.type == "formula" and not b.about:
            run.append(b)
            continue
        if run:
            parts.append(block_height(run[0], width, narrow) if len(run) == 1 else _formula_set_height(run, width))
            run = []
        if b is not None:
            parts.append(block_height(b, width, narrow))
    return sum(parts) + BLOCK_GAP_PX * max(0, len(parts) - 1)


def body_height(spec: SlideSpec) -> float:
    blocks = list(spec.blocks)
    img = image_of(spec)
    if img is not None and image_top(blocks):
        rest = [b for b in blocks if b.type != "image"]
        at = next(i for i, b in enumerate(rest) if b.type == "formula")
        top, below = rest[:at], rest[at:]
        width = content_width(spec)
        h_top = sum(block_height(b, width, True) for b in top) + BLOCK_GAP_PX * (len(top) - 1)
        h_img = min(IMAGE_TOP_MAX_PX, image_column_px(img.aspect) / max(0.2, img.aspect))
        h_below = _stack_height(below, BODY_WIDTH_PX)
        return max(h_top, h_img) + BLOCK_GAP_PX + h_below
    members = spec.layout == "members"
    main, aside = _split(blocks, members)
    narrow = img is not None
    width = content_width(spec) if narrow else MAIN_WIDTH_ASIDE_PX if aside else BODY_WIDTH_PX
    defs = [b for b in main if b.type == "definition"]
    later = trailing_definitions(main)
    if later and not members:
        # terms defined after other content: one row of cards where the first of them stands (slide.js cardRow)
        ids = {d.id for d in later}
        at = main.index(later[0])
        before = main[:at]
        after = [b for b in main[at:] if b.type != "definition" and getattr(b, "about", "") not in ids]
        h_main = _stack_height(before, width, narrow) + BLOCK_GAP_PX + _cards_height(later, main, width)
        if after:
            h_main += BLOCK_GAP_PX + _stack_height(after, width, narrow)
    elif len(defs) > 1 or (members and defs):
        # side by side (slide.js def-pair): a column / card per concept, each with its own formula / points / examples
        cols = grid_columns(len(defs))
        w = (width - MEMBER_GAP_PX * (cols - 1)) / cols
        ids = {d.id for d in defs}
        rest = [b for b in main if b.type != "definition" and getattr(b, "about", "") not in ids]

        def card(d: DefinitionBlock) -> float:
            head = 80 + block_height(d, w) if len(defs) == 2 else _member_height(d, w, cols)  # + the term heading
            return head + sum(_column_block_height(b, w) + 24 for b in main if getattr(b, "about", "") == d.id)

        rows = [defs[i:i + cols] for i in range(0, len(defs), cols)]
        grid = sum(max(card(d) for d in row) for row in rows) + MEMBER_GAP_PX * (len(rows) - 1)
        h_main = grid + sum(block_height(b, width, narrow) for b in rest) + BLOCK_GAP_PX * len(rest)
    else:
        h_main = _stack_height(main, width, narrow)
    if img is not None:
        return max(h_main, block_height(img))
    h_aside = sum(block_height(b, BODY_WIDTH_PX - MAIN_WIDTH_ASIDE_PX - 36) for b in aside) \
        + BLOCK_GAP_PX * max(0, len(aside) - 1)
    return max(h_main, h_aside)


def trailing_definitions(blocks: list) -> list[DefinitionBlock]:
    """Definitions that come after other content (mirrors slide.js trailingDefs): with at most one definition before
    that content they are drawn as one row of cards where the first of them stands. [] = the usual layouts."""
    lead: list[DefinitionBlock] = []
    later: list[DefinitionBlock] = []
    content = False
    for b in blocks:
        if b.type == "image":
            continue
        if b.type == "definition":
            (later if content else lead).append(b)
        elif not getattr(b, "about", ""):
            content = True
    return later if len(lead) <= 1 else []


def _cards_height(cards: list[DefinitionBlock], blocks: list, width: float) -> float:
    cols = grid_columns(len(cards))
    w = (width - MEMBER_GAP_PX * (cols - 1)) / cols

    def card(d: DefinitionBlock) -> float:
        return _member_height(d, w, cols) + sum(_column_block_height(b, w) + 24 for b in blocks
                                                 if getattr(b, "about", "") == d.id)

    rows = [cards[i:i + cols] for i in range(0, len(cards), cols)]
    return sum(max(card(d) for d in row) for row in rows) + MEMBER_GAP_PX * (len(rows) - 1)


COLUMN_SCALE = 0.8  # blocks in a concept column are drawn smaller (slide.css .def-col: type, padding ~0.8)


def _column_block_height(b: Block, width: float) -> float:
    """Concept-column blocks (slide.css .def-col): points are one compact card of bullet lines (28.6 px type)."""
    if b.type == "points":
        cpl = _cpl(width - 90, 28.6)
        return 36 + sum(38 * _lines(i.text, cpl) + 6 for i in b.items)
    return COLUMN_SCALE * block_height(b, width / COLUMN_SCALE)
_budget = [BODY_BUDGET_PX]  # current budget (merge(..., squeeze=True) relaxes it for one small item)
SQUEEZE = 1.25             # display auto-fit shrinks the type down to 0.8 (= 1.25 x the space), so this still fits


def fits(spec: SlideSpec) -> bool:
    # beside an image the type may shrink first (auto-fit down to 0.8) before content moves to the next part
    # (user 2026-10-06); without an image only merge(..., squeeze=True) allows that
    budget = max(_budget[0], BODY_BUDGET_PX * SQUEEZE) if image_of(spec) is not None else _budget[0]
    return body_height(spec) <= budget


def fits_unshrunk(spec: SlideSpec) -> bool:
    """Fits at the default type size (an automatic image is only added when nothing has to shrink)."""
    return body_height(spec) <= BODY_BUDGET_PX


def with_image(spec: SlideSpec, image: ImageBlock) -> SlideSpec:
    """Put (or replace) the slide's image; it is always the last block (layout follows the first)."""
    return _with_layout(spec.model_copy(update={"blocks": [b for b in spec.blocks if b.type != "image"] + [image]}))


def without_image(spec: SlideSpec) -> SlideSpec:
    return _with_layout(spec.model_copy(update={"blocks": [b for b in spec.blocks if b.type != "image"]}))


_SPLIT_LISTS = {"points": "items", "facts": "facts", "process": "steps"}


def split_to_fit(spec: SlideSpec) -> tuple[SlideSpec, list[Block]]:
    """Move the last content off a slide until it fits (the teacher put an image on a full slide). Items move one
    at a time from the end (ids kept, so the display animates them in on the next part); a block is moved whole
    when it cannot be split. Returns (the slide, moved blocks in order — [] when nothing had to move)."""
    cur = spec
    moved: list[Block] = []   # in slide order
    origin: dict[str, int] = {}  # source block id -> index in moved
    while not fits(cur):
        content = [b for b in cur.blocks if b.type != "image"]
        if not content:
            break
        last = content[-1]
        field_name = _SPLIT_LISTS.get(last.type)
        items = getattr(last, field_name) if field_name else []
        if field_name and len(items) > 1:
            kept = last.model_copy(update={field_name: items[:-1]})
            cur = _replace_block(cur, last, kept)
            if last.id in origin:
                tgt = moved[origin[last.id]]
                moved[origin[last.id]] = tgt.model_copy(update={field_name: [items[-1], *getattr(tgt, field_name)]})
            else:
                moved.insert(0, last.model_copy(update={"id": new_id(), field_name: [items[-1]]}))
                origin = {k: v + 1 for k, v in origin.items()}
                origin[last.id] = 0
        elif len(content) > 1:
            cur = _with_layout(cur.model_copy(update={"blocks": [b for b in cur.blocks if b is not last]}))
            if last.id in origin:  # its items moved already: the rest of the block joins them
                tgt = moved[origin[last.id]]
                moved[origin[last.id]] = tgt.model_copy(update={field_name: [*items, *getattr(tgt, field_name)]})
            else:
                moved.insert(0, last)
                origin = {k: v + 1 for k, v in origin.items()}
        else:
            break  # one unsplittable block: it stays (the display's auto-fit shrinks it)
    return _with_layout(cur), moved


def rejoin(spec: SlideSpec, moved: list[Block]) -> SlideSpec:
    """Undo split_to_fit: the moved blocks go back (list items to the end of the list they came from)."""
    cur = spec
    for b in moved:
        field_name = _SPLIT_LISTS.get(b.type)
        same = next((x for x in cur.blocks if x.type == b.type and field_name
                     and getattr(x, "heading", "") == getattr(b, "heading", "")), None)
        if same is not None:
            cur = _replace_block(cur, same, same.model_copy(
                update={field_name: [*getattr(same, field_name), *getattr(b, field_name)]}))
        else:
            images = [x for x in cur.blocks if x.type == "image"]
            cur = cur.model_copy(update={"blocks": [x for x in cur.blocks if x.type != "image"] + [b] + images})
    return _with_layout(cur)


def is_small(piece: Piece) -> bool:
    """One short item: better squeezed onto the slide than shown alone on the next part."""
    items = len(piece.pairs) if piece.kind == "facts" else len(piece.texts)
    return piece.kind in ("points", "example", "facts") and items <= 2 and sum(len(t) for t in piece.all_text()) <= 90


# ---- slide inspection -----------------------------------------------------------------------------------
def _find(spec: SlideSpec, block_type: str):
    """The slide-wide block of a type (blocks inside a concept column belong to that concept only)."""
    return next((b for b in spec.blocks if b.type == block_type and not getattr(b, "about", "")), None)


def _replace_block(spec: SlideSpec, old, new) -> SlideSpec:
    return spec.model_copy(update={"blocks": [new if b is old else b for b in spec.blocks]})


SUBJECT_FACETS = DEFINITION_FACETS + ("introduction", "overview")


def is_subject(spec: SlideSpec, term: str) -> bool:
    """Is the slide about this term itself (its definition slide, the term as title), or is the term one member of
    the set its facet lists ("Types": PAN, LAN ...; "Components": nodes ...; live test 2026-10-06 titled the
    Components slide "Nodes" and split the network types over three slides)?"""
    facet = (spec.facet or "").strip()
    if not facet or facet.lower() in SUBJECT_FACETS:
        return True
    return titles_match(term, facet) or titles_match(term, spec.subtitle or "")


def _with_layout(spec: SlideSpec) -> SlideSpec:
    """Layout follows the first block (the renderer styles by it); several definitions are a plain concept, and a
    slide that starts with one member of its facet's set shows it as a member card under the facet's title."""
    if not spec.blocks:
        return spec
    defs = [b for b in spec.blocks if b.type == "definition"]
    if len(defs) > 1:
        layout = "concept"
    elif defs and spec.blocks[0] is defs[0] and not is_subject(spec, defs[0].term):
        layout = "members"
    else:
        layout = BLOCK_LAYOUT.get(spec.blocks[0].type, "concept")
    return spec if spec.layout == layout else spec.model_copy(update={"layout": layout})


def _add_block(spec: SlideSpec, block: Block) -> SlideSpec:
    return _with_layout(spec.model_copy(update={"blocks": [*spec.blocks, block]}))


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
        elif b.type == "facts":
            n += len(b.facts)
        elif b.type == "groups":
            n += len(b.groups)
        elif b.type != "image":  # an image is not the teacher's content: an image-only slide is still empty
            n += 1
    return n


def has_added(spec: SlideSpec) -> bool:
    for b in spec.blocks:
        items = b.items if b.type == "points" else b.notes if b.type == "definition" else []
        if any(i.added for i in items):
            return True
        if b.id.startswith("added-"):
            return True
    return False


def _is_empty(spec: SlideSpec) -> bool:
    return teacher_items(spec) == 0 and not any(b.type not in ("points", "definition", "image") for b in spec.blocks)


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
        elif b.type == "facts":
            out += [f"{f.label} {f.value}" for f in b.facts]
    return out


def describe(spec: SlideSpec, max_items: int = 8) -> tuple[str, dict[str, str]]:
    """Summary of a slide for the interpretation prompt (CURRENT SLIDE) with numbered, revisable items.
    Returns (text, refs) where refs maps "S1" -> "slide_id/item_id"."""
    parts: list[str] = []
    refs: dict[str, str] = {}

    def ref(item_id: str, text: str) -> None:
        if len(refs) < max_items:
            key = f"S{len(refs) + 1}"
            refs[key] = f"{spec.id}/{item_id}"
            parts.append(f"[{key}] {text}")

    for b in spec.blocks:
        if b.type == "points":
            for i in b.items:
                if not i.provisional:
                    ref(i.id, i.text)
        elif b.type == "definition":
            # revisable too: a definition spoken across units arrives in pieces ("which deals" / "with the
            # composition, ...") and is completed in place (live chemistry test, session 20261005-230039-f084)
            ref(b.id, f"(definition) {b.term}: {b.definition}")
            for n in b.notes:
                if not n.provisional:
                    ref(n.id, n.text)
        elif b.type == "process":
            for s in b.steps:
                ref(s.id, f"step: {s.label}")
        elif b.type == "facts":
            for f in b.facts:
                ref(f.id, f"{f.label}: {f.value}")
        elif b.type == "groups":
            parts.append("(groups) " + "; ".join(f"{g.label}: {', '.join(i.text for i in g.items)}" for g in b.groups))
        elif b.type == "hierarchy":
            parts.append(f"(tree) {b.root.label}: " + ", ".join(c.label for c in b.root.children))
        elif b.type == "comparison":
            parts.append("(comparison) " + " vs ".join(c.heading for c in b.columns) + f", {len(b.rows)} rows")
        elif b.type == "timeline":
            parts.append("(timeline) " + "; ".join(f"{e.when} {e.label}" for e in b.events))
        elif b.type == "cause_effect":
            parts.append("(cause-effect) " + "; ".join(f"{l.cause} -> {l.effect}" for l in b.links))
        elif b.type == "formula":
            parts.append(f"(formula) {b.spoken or b.latex}")
        elif b.type in SECONDARY:
            parts.append(f"({b.type}) {b.text}")
    room = max(0, int(_budget[0] - body_height(spec)))
    head = f"{spec.title} ({spec.layout.replace('_', ' ')}, {'nearly full' if room < 120 else 'has room'})"
    return head + (": " + "; ".join(parts) if parts else ": empty"), refs


# ---- merge ----------------------------------------------------------------------------------------------
def merge(spec: SlideSpec, piece: Piece, *, full: bool = False, squeeze: bool = False
          ) -> tuple[SlideSpec, Optional[Piece]]:
    """Put a piece on a slide. Returns (new spec, leftover piece that needs another slide, or None).

    `full`: the display reported that this slide overflows; nothing more is added to it.
    `squeeze`: allow SQUEEZE × the budget (used for one small leftover instead of opening a new part).
    """
    if squeeze:
        _budget[0] = BODY_BUDGET_PX * SQUEEZE
        try:
            return merge(spec, piece, full=full)
        finally:
            _budget[0] = BODY_BUDGET_PX
    if piece.added and has_added(spec):
        log.info("dropping added piece (slide %s already has an added item): %s", spec.id, piece.all_text()[:2])
        return spec, None
    if full and not _is_empty(spec):
        return spec, piece
    if _is_empty(spec):  # nothing from the teacher yet (maybe a provisional item): the piece shapes the slide
        spec = spec.model_copy(update={"layout": LAYOUT_FOR[piece.kind],
                                       "blocks": [b for b in spec.blocks if b.type == "image"]})
    column = _column_for(spec, piece)
    if column is not None:
        out, left = _merge_column(spec, piece, column)
        return _with_layout(out), left
    out, left = _MERGERS[piece.kind](spec, piece)
    return _with_layout(out), left


# ---- concept columns: two concepts defined side by side, each with its own formula / points / examples ----
_COLUMN_KINDS = ("points", "example", "formula")


def _initials(text: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", text)).upper()


def _names(name: str, term: str) -> bool:
    """"KE" / "Kinetic energy" / "kinetic" name the term "Kinetic energy"."""
    kn, kt = term_key(name), term_key(term)  # "Polar covalent bond" does not name "Non-polar covalent bond"
    if not kn or not kt:
        return False
    if kn == kt or kn <= kt:
        return True
    compact = re.sub(r"[^A-Za-z]", "", name)
    return 2 <= len(compact) <= 4 and compact.isupper() and compact == _initials(term)


def _mentions(texts: tuple[str, ...], term: str) -> bool:
    kt = term_key(term)
    return bool(kt) and any(kt <= term_key(t) for t in texts)


def _column_for(spec: SlideSpec, piece: Piece):
    """The definition whose column a piece belongs to (live energy test 2026-10-06: the KE formula and examples
    landed under "Potential energy"). Mention in its own text wins, then the concept named by the lecture."""
    if piece.kind not in _COLUMN_KINDS:
        return None
    defs = [b for b in spec.blocks if b.type == "definition"]
    later = trailing_definitions(spec.blocks)
    if later and len(defs) - len(later) <= 1:
        # cards after other content (long test 2026-10-06): only they are columns, and only for content that
        # names them ("Bond length increases with larger atom size" under the "Bond length" card)
        texts = piece.texts if piece.kind != "formula" else ()
        named = [d for d in later if _mentions(texts, d.term)]
        if not named and len(later) == 1 and piece.about:  # one card: what follows it in the lecture (the
            d = later[0]                                     # discriminant's cases, multitopic test 411e)
            named = [d] if any(_names(s, d.term) or _mentions((s,), d.term) for s in piece.about.split("\n")) else []
        return named[0] if len(named) == 1 else None
    if len(defs) < 2 and not (defs and spec.layout == "members"):
        return None  # one member card takes its details too (the nodes' end / intermediary devices)
    if len(defs) > 2 and piece.kind == "formula":
        return None  # member cards hold no formulas
    texts = piece.texts if piece.kind != "formula" else ()
    mentioned = [d for d in defs if _mentions(texts, d.term)]
    if len(mentioned) == 1:
        return mentioned[0]
    if len(mentioned) > 1:
        return None  # about several: full width below
    if piece.meta.get("carried") and len(defs) > 1 and not all(len(t.split()) <= 4 for t in piece.texts) \
            and not any(b.type == "formula" for b in spec.blocks):  # a formula's statements continue in the next
        # unit ("Discriminant < 0: two complex roots" after D = b² - 4ac, multitopic test 411e)
        # full statements of the next unit that name no concept, with several concepts on the slide: general (the
        # properties of covalent compounds after the non-polar and polar cards, long test 2026-10-06); short items
        # ("rolling ball" after the KE formula) and the details of a single member card still follow it
        return None
    for segment in reversed(piece.about.split("\n") if piece.about else []):  # the newest named concept first
        named = [d for d in defs if _names(segment, d.term) or _mentions((segment,), d.term)]
        if len(named) == 1:
            return named[0]
        if named:
            return None
    return None


def member_of(spec: SlideSpec, piece: Piece) -> Optional[DefinitionBlock]:
    """The member card (of a slide listing a set's members) that a piece is about; None for concept columns."""
    defs = sum(1 for b in spec.blocks if b.type == "definition")
    if spec.layout != "members" and defs < 3:
        return None
    return _column_for(spec, piece)


def is_about(piece: Piece, term: str) -> bool:
    """Is the piece about this concept (its definition again, a mention, or the concept the lecture named)?"""
    if piece.kind == "definition":
        return same_term(piece.term, term)
    if _mentions(piece.texts, term):
        return True
    return any(_names(s, term) or _mentions((s,), term) for s in piece.about.split("\n") if s)


def _merge_column(spec: SlideSpec, piece: Piece, db: DefinitionBlock) -> tuple[SlideSpec, Optional[Piece]]:
    mine = [b for b in spec.blocks if getattr(b, "about", "") == db.id]
    if piece.kind == "formula":
        f = piece.formula
        assert f is not None
        if any(b.type == "formula" and is_duplicate(b.spoken or b.latex, f.expression) for b in spec.blocks):
            return spec, None
        if any(b.type == "formula" for b in mine):
            return spec, piece  # one formula per concept column; the next one continues on the next part
        variables = [_variable(s, m) for s, m in f.variables[:CAPACITY["variables"]]]
        cand = _add_block(spec, FormulaBlock(latex=to_latex(f.expression), spoken=f.expression, variables=variables,
                                             about=db.id))
        return (cand, None) if fits(cand) else (spec, piece)
    fresh = _new(_texts_on(spec), piece.texts)
    if piece.added:
        fresh = fresh[:1]
    if not fresh:
        return spec, None
    if piece.kind == "example":
        eb = next((b for b in mine if b.type == "example"), None)
        text = "; ".join(fresh)
        cand = (_replace_block(spec, eb, eb.model_copy(update={"text": f"{eb.text}; {text}"})) if eb
                else _add_block(spec, ExampleBlock(text=text, about=db.id)))
        return (cand, None) if fits(cand) else (spec, piece)
    pb = next((b for b in mine if b.type == "points"), None)
    defs = sum(1 for b in spec.blocks if b.type == "definition")
    # a member card among several keeps a few details; a member explained in more depth gets its own slide
    limit = CAPACITY["member_points"] if defs > 2 else CAPACITY["points"]
    if pb is not None:
        room = max(0, limit - len(pb.items))
        out, rest = _greedy(spec, fresh[:room], lambda ts: _replace_block(
            spec, pb, pb.model_copy(update={"items": pb.items + _items(ts, piece.added)})))
        rest += fresh[room:]
    else:
        out, rest = _greedy(spec, fresh[:limit], lambda ts: _add_block(
            spec, PointsBlock(items=_items(ts, piece.added), about=db.id)))
        rest += fresh[limit:]
    if out is spec:
        return spec, piece
    return out, piece.with_texts(rest) if rest else None


def _greedy(spec: SlideSpec, items: list, build: Callable[[list], SlideSpec]) -> tuple[SlideSpec, list]:
    """Add as many of `items` as fit the space budget (build(prefix) → spec with that prefix added).
    An empty slide always takes at least one item, so nothing can get stuck."""
    best, n = spec, 0
    for k in range(1, len(items) + 1):
        cand = build(items[:k])
        if not fits(cand) and (k > 1 or spec.blocks):
            break
        best, n = cand, k
    return best, list(items[n:])


def _items(texts: list[str], added: bool) -> list[Item]:
    return [Item(text=t, added=added) for t in texts]


def _merge_points(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    label = piece.term
    # a heading belongs to the items it came with: unlabelled points never join a labelled list, and a labelled
    # list never takes over earlier unlabelled points (live test 2026-10-06: "Low power consumption" under
    # "Common programming languages"; speed / latency under "5G core application scenarios")
    pb = next((b for b in spec.blocks if b.type == "points" and not b.about
               and (titles_match(b.heading, label) if label and b.heading else not label and not b.heading)), None)
    fresh = _new(_texts_on(spec), piece.texts)
    if piece.added:
        fresh = fresh[:1]
    if not fresh:
        return spec, None
    if pb is not None:
        kept = [i for i in pb.items if not i.provisional]
        prov = [i for i in pb.items if i.provisional]
        room = max(0, CAPACITY["points"] - len(kept))
        heading = pb.heading
        out, rest = _greedy(spec, fresh[:room], lambda ts: _replace_block(spec, pb, pb.model_copy(
            update={"heading": heading, "items": kept + _items(ts, piece.added) + prov})))
        rest += fresh[room:]
        return out, piece.with_texts(rest) if rest else None
    if any(b.type in LARGE for b in spec.blocks) and len(fresh) == 1 \
            and sum(1 for b in spec.blocks if b.type in SECONDARY) < CAPACITY["secondary"]:
        block = CalloutBlock(kind="note", text=fresh[0])  # one remark next to a diagram: a note card
        if piece.added:
            block = block.model_copy(update={"id": "added-" + block.id})
        cand = _add_block(spec, block)
        if fits(cand):
            return cand, None
    out, rest = _greedy(spec, fresh[:CAPACITY["points"]], lambda ts: _add_block(
        spec, PointsBlock(heading=label, items=_items(ts, piece.added))))
    rest += fresh[CAPACITY["points"]:]
    if out is spec:
        return spec, piece
    return out, piece.with_texts(rest) if rest else None


def _add_note(spec: SlideSpec, db: DefinitionBlock, piece: Piece, text: str) -> tuple[SlideSpec, Optional[Piece]]:
    """A short note chip under a definition (word parts: "photo means light"); a list item when notes are full."""
    if any(is_duplicate(text, t) for t in _texts_on(spec)):
        return spec, None
    kept = [n for n in db.notes if not n.provisional]
    if len(kept) < CAPACITY["notes"] and len(text) <= 60:
        cand = _replace_block(spec, db, db.model_copy(update={"notes": kept + _items([text], piece.added)}))
        if fits(cand):
            return cand, None
    return _merge_points(spec, Piece("points", lines=piece.lines, added=piece.added, texts=(text,)))


def _merge_definition(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    defs = [b for b in spec.blocks if b.type == "definition"]
    for db in defs:
        if same_term(db.term, piece.term):
            if is_duplicate(db.definition, piece.definition):
                return spec, None
            return _merge_points(spec, Piece("points", lines=piece.lines, added=piece.added,
                                             texts=(piece.definition,)))
        if _is_part_term(piece.term, db.term) or piece.definition.split(" ", 1)[0].lower() in ("means", "stands"):
            return _add_note(spec, db, piece, term_note(piece.term, piece.definition))
    block = DefinitionBlock(term=cap(piece.term), definition=piece.definition)
    if not spec.blocks:
        out = _add_block(spec, block)
        if spec.facet and spec.facet.strip().lower() in DEFINITION_FACETS:
            out = out.model_copy(update={"title": what_is(_lower_term(piece.term))})  # the term, not the topic
        return out, None
    if not defs:  # a new term introduced on a slide with other content: a definition card below it, if room
        cand = _add_block(spec, block)
        return (cand, None) if fits(cand) else (spec, piece)
    # a peer concept defined alongside (elements and compounds, atoms and molecules): side-by-side definitions.
    # The topic's own definition is no peer: live kinematics test 2026-10-06 paired "Kinematics" with "Distance" and
    # pushed "Displacement" to another slide; now distance + displacement go together on the next part.
    # exact key: "Kinetic energy" is a peer concept under the topic "Energy", not the topic itself
    # More members of one set (PAN, LAN, MAN, WAN under "Types"): member cards on the same slide, up to 6 (live test
    # 2026-10-06 split them over three slides). An automatic image yields to them (the image policy blocks images
    # beside several definitions); member cards hold no formulas, so concept columns with formulas stay two.
    topic_def = any(title_key(d.term) and title_key(d.term) == title_key(spec.subtitle or "") for d in defs)
    img = image_of(spec)
    base = without_image(spec) if img is not None and img.origin == "auto" else spec
    ids = {d.id for d in defs}
    others = [b for b in base.blocks if b.type not in ("definition", "image")]
    if len(defs) < CAPACITY["definitions"] and not topic_def \
            and all(b.type in SECONDARY or getattr(b, "about", "") in ids for b in others) \
            and (len(defs) > 1 or not any(not n.provisional for n in defs[0].notes)) \
            and (len(defs) < 2 or not any(b.type == "formula" for b in others)):
        base = clear_provisional(base)  # a teaser note must not block the pairing
        cand = _add_block(base, block)
        cand = cand.model_copy(update={"blocks": [b for b in cand.blocks if b.type == "definition"]
                                       + [b for b in cand.blocks if b.type != "definition"]})
        if len(defs) == 1 and spec.title == what_is(_lower_term(defs[0].term)):
            # "What is distance?" → "Distance and displacement"
            cand = cand.model_copy(update={"title": f"{cap(defs[0].term)} and {_lower_term(piece.term)}"})
        elif len(defs) == 2 and spec.title == f"{cap(defs[0].term)} and {_lower_term(defs[1].term)}":
            cand = cand.model_copy(update={"title": slide_title(spec.subtitle, spec.facet or "")})
        if fits(cand):
            return _with_layout(cand), None
    asks_one = (spec.facet or "").strip().lower() in DEFINITION_FACETS  # "What is X?": another term, another slide
    if not asks_one and len(defs) < CAPACITY["definitions"] \
            and any(b.type not in SECONDARY and not getattr(b, "about", "") for b in others):
        # a term defined after other content (points, a list): a card below it on the same slide, several in a
        # row (long test 2026-10-06: "Dipole-induced dipole forces", "Hydrogen bond", "Thermal energy" opened a part
        # II while part I was two thirds empty). Only when the slide is full does it open the next part.
        cand = _add_block(spec, block)
        if fits(cand):
            return _with_layout(cand), None
    return spec, piece


def _merge_facts(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    fb = _find(spec, "facts")
    existing = [f"{f.label} {f.value}" for f in fb.facts] if fb else []
    labels = {_norm(f.label) for f in fb.facts} if fb else set()
    fresh = [(a, b) for a, b in piece.pairs
             if not any(is_duplicate(f"{a} {b}", e) for e in existing) and _norm(a) not in labels]
    if not fresh:
        return spec, None
    if fb is None:
        out, rest = _greedy(spec, fresh[:CAPACITY["facts"]], lambda fs: _add_block(
            spec, FactsBlock(facts=[Fact(label=a, value=b) for a, b in fs])))
        rest += fresh[CAPACITY["facts"]:]
        if out is spec:
            return spec, piece
    else:
        room = max(0, CAPACITY["facts"] - len(fb.facts))
        out, rest = _greedy(spec, fresh[:room], lambda fs: _replace_block(spec, fb, fb.model_copy(
            update={"facts": fb.facts + [Fact(label=a, value=b) for a, b in fs]})))
        rest += fresh[room:]
    return out, replace(piece, pairs=tuple(rest)) if rest else None


def classification_label(label: str, topic: str) -> str:
    """A group's label among several classifications of one thing: "Microcontroller types by bit width" -> "By bit
    width", "Microcontroller Architecture Types" -> "Architecture Types" (the crumb already names the topic)."""
    m = re.search(r"\bby\s+(\S.*)$", label, re.IGNORECASE)
    if m:
        return "By " + m.group(1)
    words, topic_key = label.split(), title_key(topic)
    while len(words) > 1 and title_key(words[0]) and title_key(words[0]) <= topic_key:
        words = words[1:]
    return cap(" ".join(words))


# ---- sub-classifications (verify round 4 step D, user 2026-10-06) -------------------------------------
# A kind of a classification divided further ("Matter" -> physical / chemical; physical -> solid, liquid, gas) grows
# the tree a level instead of turning it into equal group cards: the chart shows what belongs under what.
TREE_GAP_PX = 28        # slide.css .tree-children gap
TREE_NODE_PAD_PX = 68   # .tree-node horizontal padding
TREE_MAX_DEPTH = 3      # the root and two levels below it
_TREE_FONT = (42, 34, 26)  # root, first level, deeper levels (slide.css)


def tree_depth(n: TreeNode) -> int:
    return 1 + max((tree_depth(c) for c in n.children), default=0)


def tree_width(n: TreeNode, level: int = 0) -> float:
    """Estimated width of the drawn tree (design px): a node is as wide as its label or as all its children."""
    own = len(n.label) * _TREE_FONT[min(level, 2)] * 0.55 + TREE_NODE_PAD_PX
    if not n.children:
        return own
    kids = sum(tree_width(c, level + 1) for c in n.children) + TREE_GAP_PX * (len(n.children) - 1)
    return max(own, kids)


def subdivide(root: TreeNode, divisions: tuple[tuple[str, tuple[str, ...]], ...]) -> Optional[TreeNode]:
    """The tree with each division's kinds under the node it divides (same ids for what was there: nothing
    re-animates), or None when a division names no single node below the root, or the tree gets too deep or too
    wide for the slide."""
    def find(n: TreeNode, label: str, level: int) -> list[str]:
        hits = [n.id] if level > 0 and titles_match(n.label, label) else []
        return hits + [h for c in n.children for h in find(c, label, level + 1)]

    targets: dict[str, tuple[str, ...]] = {}
    for label, kinds in divisions:
        hits = find(root, label, 0)
        if len(hits) != 1 or not kinds:
            return None
        targets[hits[0]] = kinds

    def grow(n: TreeNode) -> TreeNode:
        children = [grow(c) for c in n.children]
        if n.id in targets:
            fresh = _new([c.label for c in children], targets[n.id])[: max(0, CAPACITY["tree"] - len(children))]
            children += [TreeNode(label=cap(t)) for t in fresh]
        return n.model_copy(update={"children": children})

    out = grow(root)
    if tree_depth(out) > TREE_MAX_DEPTH or tree_width(out) > BODY_WIDTH_PX:
        log.info("tree %r would be too deep or too wide with %s", root.label, [d for d, _ in divisions])
        return None
    return out


def _merge_groups(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    orig = spec
    hb = _find(spec, "hierarchy")
    if hb is not None and _find(spec, "groups") is None:
        grown = subdivide(hb.root, piece.groups)
        if grown is not None:  # the kinds of the tree's own kinds: one tree, a level deeper
            cand = _replace_block(spec, hb, hb.model_copy(update={"root": grown}))
            return (cand, None) if fits(cand) or len(spec.blocks) == 1 else (orig, piece)
        # several classifications of one thing (by bits, by memory, by instruction set ...) are one set of group
        # cards; the classification shown as a tree so far becomes the first card (same ids: nothing re-animates)
        spec = _replace_block(spec, hb, GroupsBlock(id=hb.id, groups=[Group(
            id=hb.root.id, label=hb.root.label, items=[Item(id=c.id, text=c.label) for c in hb.root.children])]))
    gb = _find(spec, "groups")
    if gb is not None:
        groups = list(gb.groups)
        for label, items in piece.groups:
            short = classification_label(label, spec.subtitle)
            g = next((x for x in groups if titles_match(x.label, label) or titles_match(x.label, short)), None)
            if g is None:
                if len(groups) >= CAPACITY["groups"]:
                    log.info("groups block full; %r continues on the next part", label)
                    return orig, piece
                groups.append(Group(label=label, items=_items(list(items[:CAPACITY["group_items"]]), piece.added)))
            else:
                fresh = _new([i.text for i in g.items], items)[: max(0, CAPACITY["group_items"] - len(g.items))]
                groups[groups.index(g)] = g.model_copy(update={"items": g.items + _items(fresh, piece.added)})
        if len(groups) > 1:
            groups = [g.model_copy(update={"label": classification_label(g.label, spec.subtitle)}) for g in groups]
        cand = _replace_block(spec, gb, gb.model_copy(update={"groups": groups}))
        return (cand, None) if fits(cand) or len(spec.blocks) == 1 else (orig, piece)
    block = GroupsBlock(heading=piece.term, groups=[
        Group(label=lb, items=_items(list(its[:CAPACITY["group_items"]]), piece.added))
        for lb, its in piece.groups[:CAPACITY["groups"]]])
    cand = _add_block(spec, block)
    return (cand, None) if fits(cand) or not spec.blocks else (spec, piece)


def _merge_tree(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    hb = _find(spec, "hierarchy")
    if hb is not None and titles_match(hb.root.label, piece.term):
        room = max(0, CAPACITY["tree"] - len(hb.root.children))
        all_fresh = _new([c.label for c in hb.root.children], piece.texts)
        fresh = all_fresh[:room]
        if len(all_fresh) > room:
            log.info("tree %r is full; not shown: %s", hb.root.label, all_fresh[room:])
        root = hb.root.model_copy(update={"children": hb.root.children + [TreeNode(label=t) for t in fresh]})
        return _replace_block(spec, hb, hb.model_copy(update={"root": root})), None
    if hb is not None:
        grown = subdivide(hb.root, ((piece.term, piece.texts),))
        if grown is not None:  # one of the tree's kinds divided further
            cand = _replace_block(spec, hb, hb.model_copy(update={"root": grown}))
            if fits(cand) or len(spec.blocks) == 1:
                return cand, None
    if hb is not None or _find(spec, "groups") is not None:
        # a further classification on the slide: all of them read best as named groups side by side
        return _merge_groups(spec, Piece("groups", lines=piece.lines, added=piece.added,
                                         groups=((piece.term, piece.texts),)))
    if any(b.type in LARGE for b in spec.blocks):
        return spec, piece
    block = HierarchyBlock(root=TreeNode(label=piece.term, children=[TreeNode(label=t)
                                                                     for t in piece.texts[:CAPACITY["tree"]]]))
    cand = _add_block(spec, block)
    if fits(cand) or not spec.blocks:
        return cand, None
    # no room for the diagram: the kinds as a labelled list may still fit, all of them (live test 2026-10-06:
    # "Ovaries" alone under "Female reproductive organs", the other five on the next part)
    out, left = _merge_points(spec, Piece("points", lines=piece.lines, added=piece.added, term=piece.term,
                                          texts=piece.texts))
    return (out, None) if left is None else (spec, piece)


def _merge_steps(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    pb = _find(spec, "process")
    if pb is None:
        if any(b.type in LARGE for b in spec.blocks) or len(spec.blocks) > 1:
            return spec, piece
        pb = ProcessBlock()
        base = _add_block(spec, pb)
    else:
        base = spec
    fresh = _new([s.label for s in pb.steps], piece.texts)
    room = max(0, CAPACITY["steps"] - len(pb.steps))
    out, rest = _greedy(spec, fresh[:room], lambda ts: _replace_block(
        base, pb, pb.model_copy(update={"steps": pb.steps + [Step(label=t) for t in ts]})))
    rest += fresh[room:]
    if out is spec:
        return spec, (piece.with_texts(rest) if rest else None) if pb.steps else piece
    return out, piece.with_texts(rest) if rest else None


def _merge_comparison(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    cb = _find(spec, "comparison")
    if cb is None:
        if any(b.type in LARGE for b in spec.blocks):
            return spec, piece
        cols = list(piece.columns) or ["", ""]
        width = max(len(cols), max((len(c) for _, c in piece.rows), default=0))
        cols = (cols + [""] * width)[:min(width, CAPACITY["columns"])]
        cb = ComparisonBlock(columns=[Column(heading=cap(h)) for h in cols])
        base = _add_block(spec, cb)
    elif piece.columns and not _same_columns([c.heading for c in cb.columns], list(piece.columns)):
        return spec, piece
    else:
        base = spec
    n = len(cb.columns)
    existing = [r.aspect + " " + " ".join(r.cells) for r in cb.rows]
    rows = []
    for aspect, cells in piece.rows:
        text = aspect + " " + " ".join(cells)
        if any(is_duplicate(text, e) for e in existing):
            continue
        existing.append(text)
        rows.append(Row(aspect=cap(aspect), cells=(list(cells) + [""] * n)[:n]))
    room = max(0, CAPACITY["rows"] - len(cb.rows))
    out, rest = _greedy(spec if base is not spec and rows else base, rows[:room], lambda rs: _replace_block(
        base, cb, cb.model_copy(update={"rows": cb.rows + rs})))
    rest += rows[room:]
    if out is spec and base is not spec:
        if not rows:
            return (base, None) if fits(base) or not spec.blocks else (spec, piece)
        return spec, piece
    if rest:
        return out, replace(piece, rows=tuple((r.aspect, tuple(r.cells)) for r in rest),
                            columns=tuple(c.heading for c in cb.columns))
    return out, None


def _same_columns(a: list[str], b: list[str]) -> bool:
    a = [x for x in a if x]
    b = [x for x in b if x]
    return not a or not b or (len(a) >= len(b) and all(any(titles_match(x, y) for y in a) for x in b))


def _merge_pairs(block_type: str, cap_key: str):
    def merge_fn(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
        blk = _find(spec, block_type)
        if blk is None:
            if any(b.type in LARGE for b in spec.blocks) or len(spec.blocks) > 1:
                return spec, piece
            blk = TimelineBlock() if block_type == "timeline" else CauseEffectBlock()
            base = _add_block(spec, blk)
        else:
            base = spec
        field = "events" if block_type == "timeline" else "links"
        current = getattr(blk, field)
        if block_type == "timeline":
            existing = [f"{e.when} {e.label}" for e in current]
            make = lambda a, b: TimelineEvent(when=a, label=b)  # noqa: E731
        else:
            existing = [f"{l.cause} {l.effect}" for l in current]
            make = lambda a, b: CauseLink(cause=a, effect=b)  # noqa: E731
        fresh = []
        for a, b in piece.pairs:
            if not any(is_duplicate(f"{a} {b}", e) for e in existing):
                existing.append(f"{a} {b}")
                fresh.append((a, b))
        room = max(0, CAPACITY[cap_key] - len(current))
        out, rest = _greedy(spec, fresh[:room], lambda ps: _replace_block(
            base, blk, blk.model_copy(update={field: current + [make(a, b) for a, b in ps]})))
        rest += fresh[room:]
        if out is spec and not current:
            return spec, piece
        return out, replace(piece, pairs=tuple(rest)) if rest else None
    return merge_fn


def _variable(symbol: str, meaning: str) -> Variable:
    return Variable(symbol=symbol, meaning=meaning, latex=to_latex(symbol))


def _merge_formula(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    f = piece.formula
    assert f is not None
    formulas = [b for b in spec.blocks if b.type == "formula" and not b.about]
    if any(is_duplicate(fb.spoken or fb.latex, f.expression) for fb in formulas):
        return spec, None
    if any(b.type in LARGE and b.type != "formula" for b in spec.blocks):
        return spec, piece
    if formulas and (len(formulas) >= CAPACITY["formulas"] or spec.blocks[-1].type != "formula"
                     or spec.blocks[-1].about):
        # formulas said together form one set (round 5: the equations of motion were three slides); only when the
        # new one directly follows a slide-wide formula, so the set stays one stack
        return spec, piece
    variables = [_variable(s, m) for s, m in f.variables[:CAPACITY["variables"]]]
    cand = _add_block(spec, FormulaBlock(latex=to_latex(f.expression), spoken=f.expression, variables=variables))
    return (cand, None) if fits(cand) or not spec.blocks else (spec, piece)


def _merge_example(spec: SlideSpec, piece: Piece) -> tuple[SlideSpec, Optional[Piece]]:
    text = piece.texts[0]
    if any(is_duplicate(text, t) for t in _texts_on(spec)):
        return spec, None
    block = ExampleBlock(text=text)
    if piece.added:
        block = block.model_copy(update={"id": "added-" + block.id})
    if not spec.blocks:
        return _add_block(spec, block), None
    eb = next((b for b in spec.blocks if b.type == "example" and not b.about and not b.id.startswith("added-")), None)
    if eb is not None and not piece.added:  # a further example joins the example card (live energy test: a lone
        cand = _replace_block(spec, eb, eb.model_copy(update={"text": f"{eb.text}; {text}"}))  # "compressed spring"
        if fits(cand):                                                                         # opened a part)
            return cand, None
    if sum(1 for b in spec.blocks if b.type in SECONDARY) < CAPACITY["secondary"]:
        cand = _add_block(spec, block)
        if fits(cand):
            return cand, None
    return spec, piece


_MERGERS = {
    "points": _merge_points, "definition": _merge_definition, "steps": _merge_steps,
    "comparison": _merge_comparison, "timeline": _merge_pairs("timeline", "events"),
    "causes": _merge_pairs("cause_effect", "links"), "formula": _merge_formula, "example": _merge_example,
    "facts": _merge_facts, "groups": _merge_groups, "tree": _merge_tree,
}


# ---- in-place edits (revisions, correction toggles) -----------------------------------------------------
def _definition_text(term: str, text: str) -> str:
    """A revised definition may repeat the term ("Chemistry: the branch ...", "Chemistry is the branch ...")."""
    t = drop_self_alias(text.strip(), term)
    if term and t.lower().startswith(term.lower()):
        rest = t[len(term):].lstrip()
        if rest.startswith("(") and ")" in rest:  # "Ionic Bond (Electrovalent Bond): ..." (long test 2026-10-06)
            rest = rest[rest.index(")") + 1:].lstrip()
        for lead in (":", "-", "–", "is ", "means "):
            if rest.lower().startswith(lead):
                return rest[len(lead):].strip() or t
    return t


def revise_item(spec: SlideSpec, item_id: str, text: str) -> Optional[SlideSpec]:
    """Rewrite one item in place (same id: the display updates just that text). None if the id is not here."""
    blocks = []
    hit = False
    for b in spec.blocks:
        if b.type == "points" and any(i.id == item_id for i in b.items):
            b = b.model_copy(update={"items": [i.model_copy(update={"text": text, "provisional": False})
                                               if i.id == item_id else i for i in b.items]})
            hit = True
        elif b.type == "definition" and b.id == item_id:
            b = b.model_copy(update={"definition": _definition_text(b.term, text)})
            hit = True
        elif b.type == "definition" and any(n.id == item_id for n in b.notes):
            b = b.model_copy(update={"notes": [n.model_copy(update={"text": text}) if n.id == item_id else n
                                               for n in b.notes]})
            hit = True
        elif b.type == "process" and any(s.id == item_id for s in b.steps):
            b = b.model_copy(update={"steps": [s.model_copy(update={"label": text}) if s.id == item_id else s
                                               for s in b.steps]})
            hit = True
        elif b.type == "facts" and any(f.id == item_id for f in b.facts):
            label, sep, value = text.partition(":")
            b = b.model_copy(update={"facts": [
                (f.model_copy(update={"label": label.strip(), "value": value.strip()}) if sep
                 else f.model_copy(update={"value": text})) if f.id == item_id else f for f in b.facts]})
            hit = True
        blocks.append(b)
    return spec.model_copy(update={"blocks": blocks}) if hit else None


# ---- the teacher's edits (live slide editing in /control, F-008) ----------------------------------------
TERM_SUFFIX = ":term"  # "<definition id>:term" = the term of a definition card


def edit_text(spec: SlideSpec, item_id: str, text: str) -> Optional[SlideSpec]:
    """The teacher's text for one element, exactly as typed (same id: only that text changes on the display).
    None if the element is not on this slide or cannot be edited as text (a formula, an image)."""
    def walk(n: TreeNode) -> TreeNode:
        return n.model_copy(update={"label": text if n.id == item_id else n.label,
                                    "children": [walk(c) for c in n.children]})

    blocks, hit = [], False
    for b in spec.blocks:
        new = b
        if b.type == "definition":
            if item_id == b.id + TERM_SUFFIX:
                new = b.model_copy(update={"term": text})
            elif item_id == b.id:
                new = b.model_copy(update={"definition": text})
            elif any(n.id == item_id for n in b.notes):
                new = b.model_copy(update={"notes": [n.model_copy(update={"text": text, "provisional": False})
                                                     if n.id == item_id else n for n in b.notes]})
        elif b.type == "points" and any(i.id == item_id for i in b.items):
            new = b.model_copy(update={"items": [i.model_copy(update={"text": text, "provisional": False, "added": False})
                                                 if i.id == item_id else i for i in b.items]})
        elif b.type == "process" and any(s.id == item_id for s in b.steps):
            new = b.model_copy(update={"steps": [s.model_copy(update={"label": text, "detail": ""})
                                                 if s.id == item_id else s for s in b.steps]})
        elif b.type == "facts" and any(f.id == item_id for f in b.facts):
            label, sep, value = text.partition(":")
            new = b.model_copy(update={"facts": [
                f.model_copy(update={"label": label.strip() if sep else text, "value": value.strip() if sep else ""})
                if f.id == item_id else f for f in b.facts]})
        elif b.type == "groups" and any(g.id == item_id or any(i.id == item_id for i in g.items) for g in b.groups):
            new = b.model_copy(update={"groups": [g.model_copy(update={
                "label": text if g.id == item_id else g.label,
                "items": [i.model_copy(update={"text": text}) if i.id == item_id else i for i in g.items]})
                for g in b.groups]})
        elif b.type == "hierarchy" and item_id in element_texts(spec.model_copy(update={"blocks": [b]})):
            new = b.model_copy(update={"root": walk(b.root)})
        elif b.type in SECONDARY and b.id == item_id:
            new = b.model_copy(update={"text": text})
        hit = hit or new is not b
        blocks.append(new)
    return spec.model_copy(update={"blocks": blocks}) if hit else None


def add_point(spec: SlideSpec, text: str) -> tuple[SlideSpec, str]:
    """A point the teacher adds: to the slide's own list (not a concept column's), else a new list at the end."""
    item = Item(text=text)
    pb = _find(spec, "points")
    if pb is not None:
        return _replace_block(spec, pb, pb.model_copy(update={"items": [*pb.items, item]})), item.id
    return _add_block(spec, PointsBlock(items=[item])), item.id


def element_texts(spec: SlideSpec) -> dict[str, str]:
    """Every addressable element id on the slide → its text (items, steps, facts, rows, nodes, whole blocks)."""
    out: dict[str, str] = {}

    def walk(n: TreeNode) -> None:
        out[n.id] = n.label
        for c in n.children:
            walk(c)

    for b in spec.blocks:
        if b.type == "points":
            out.update({i.id: i.text for i in b.items})
        elif b.type == "definition":
            out[b.id] = f"{b.term} {b.definition}"
            out.update({n.id: n.text for n in b.notes})
        elif b.type == "process":
            out.update({s.id: s.label for s in b.steps})
        elif b.type == "facts":
            out.update({f.id: f"{f.label} {f.value}" for f in b.facts})
        elif b.type == "groups":
            for g in b.groups:
                out[g.id] = g.label
                out.update({i.id: i.text for i in g.items})
        elif b.type == "hierarchy":
            walk(b.root)
        elif b.type == "comparison":
            out.update({r.id: " ".join([r.aspect, *r.cells]) for r in b.rows})
        elif b.type == "timeline":
            out.update({e.id: f"{e.when} {e.label}" for e in b.events})
        elif b.type == "cause_effect":
            out.update({l.id: f"{l.cause} {l.effect}" for l in b.links})
        elif b.type != "image":  # an image has no slide text (never a correction target, never in the prompt)
            out[b.id] = getattr(b, "text", "") or getattr(b, "spoken", "") or getattr(b, "latex", "")
    return out


def remove_elements(spec: SlideSpec, ids: set[str]) -> SlideSpec:
    """Drop elements by id — every kind element_texts() reports (items, notes, steps, facts, groups and their items,
    tree nodes, rows, events, links, whole blocks); blocks left empty are removed."""
    def prune(n: TreeNode) -> Optional[TreeNode]:
        if n.id in ids:
            return None
        kids = [c for c in (prune(k) for k in n.children) if c is not None]
        return n.model_copy(update={"children": kids})

    blocks = []
    for b in spec.blocks:
        if b.id in ids:
            continue
        if b.type == "points":
            b = b.model_copy(update={"items": [i for i in b.items if i.id not in ids]})
            if not b.items:
                continue
        elif b.type == "definition":
            b = b.model_copy(update={"notes": [n for n in b.notes if n.id not in ids]})
        elif b.type == "facts":
            b = b.model_copy(update={"facts": [f for f in b.facts if f.id not in ids]})
            if not b.facts:
                continue
        elif b.type == "process":
            b = b.model_copy(update={"steps": [x for x in b.steps if x.id not in ids]})
            if not b.steps:
                continue
        elif b.type == "groups":
            groups = [g.model_copy(update={"items": [i for i in g.items if i.id not in ids]})
                      for g in b.groups if g.id not in ids]
            groups = [g for g in groups if g.items]
            if not groups:
                continue
            b = b.model_copy(update={"groups": groups})
        elif b.type == "hierarchy":
            root = prune(b.root)
            if root is None or not root.children:
                continue
            b = b.model_copy(update={"root": root})
        elif b.type == "comparison":
            b = b.model_copy(update={"rows": [r for r in b.rows if r.id not in ids]})
            if not b.rows:
                continue
        elif b.type == "timeline":
            b = b.model_copy(update={"events": [e for e in b.events if e.id not in ids]})
            if not b.events:
                continue
        elif b.type == "cause_effect":
            b = b.model_copy(update={"links": [l for l in b.links if l.id not in ids]})
            if not b.links:
                continue
        blocks.append(b)
    if all(b.type == "image" for b in blocks):
        blocks = []  # an image without the content it illustrated does not stay
    return _with_layout(spec.model_copy(update={"blocks": blocks}))


def _sub(text: str, old: str, new: str) -> str:
    """Whole-word, case-insensitive replacement; the replacement is literal (backslashes are text) and takes the
    capitalisation of what it replaces ("venus" at a sentence start stays "Venus")."""
    if not old:
        return text

    def repl(m: re.Match) -> str:
        found = m.group(0)
        if found[:1].isupper() and new[:1].islower():
            return new[:1].upper() + new[1:]
        if found[:1].islower() and new[:1].isupper() and not new[1:2].isupper():
            return new[:1].lower() + new[1:]
        return new

    return re.sub(rf"(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])", repl, text, flags=re.IGNORECASE)


def substitute(spec: SlideSpec, ids: set[str], old: str, new: str) -> SlideSpec:
    """Replace a word span in the given elements only (correction shown / reverted to what was said)."""
    s = lambda t: _sub(t, old, new)  # noqa: E731

    def walk(n: TreeNode) -> TreeNode:
        return n.model_copy(update={"label": s(n.label) if n.id in ids else n.label,
                                    "children": [walk(c) for c in n.children]})

    blocks = []
    for b in spec.blocks:
        if b.type == "points":
            b = b.model_copy(update={"items": [i.model_copy(update={"text": s(i.text)}) if i.id in ids else i
                                               for i in b.items]})
        elif b.type == "definition":
            if b.id in ids:
                b = b.model_copy(update={"term": s(b.term), "definition": s(b.definition)})
            b = b.model_copy(update={"notes": [n.model_copy(update={"text": s(n.text)}) if n.id in ids else n
                                               for n in b.notes]})
        elif b.type == "process":
            b = b.model_copy(update={"steps": [x.model_copy(update={"label": s(x.label)}) if x.id in ids else x
                                               for x in b.steps]})
        elif b.type == "facts":
            b = b.model_copy(update={"facts": [f.model_copy(update={"label": s(f.label), "value": s(f.value)})
                                               if f.id in ids else f for f in b.facts]})
        elif b.type == "groups":
            b = b.model_copy(update={"groups": [g.model_copy(update={
                "label": s(g.label) if g.id in ids else g.label,
                "items": [i.model_copy(update={"text": s(i.text)}) if i.id in ids else i for i in g.items]})
                for g in b.groups]})
        elif b.type == "hierarchy":
            b = b.model_copy(update={"root": walk(b.root)})
        elif b.type == "comparison":
            b = b.model_copy(update={"rows": [r.model_copy(update={"aspect": s(r.aspect),
                                                                   "cells": [s(c) for c in r.cells]})
                                              if r.id in ids else r for r in b.rows]})
        elif b.type == "timeline":
            b = b.model_copy(update={"events": [e.model_copy(update={"label": s(e.label)}) if e.id in ids else e
                                                for e in b.events]})
        elif b.type == "cause_effect":
            b = b.model_copy(update={"links": [l.model_copy(update={"cause": s(l.cause), "effect": s(l.effect)})
                                               if l.id in ids else l for l in b.links]})
        elif b.id in ids:
            if b.type == "formula":
                spoken = s(b.spoken or b.latex)  # edit the words as said, then rebuild the LaTeX
                b = b.model_copy(update={"latex": to_latex(spoken), "spoken": spoken,
                                         "variables": [_variable(s(v.symbol), v.meaning) for v in b.variables]})
            elif b.type in SECONDARY:
                b = b.model_copy(update={"text": s(b.text)})
        blocks.append(b)
    return spec.model_copy(update={"blocks": blocks})


# ---- provisional fast path ------------------------------------------------------------------------------
def set_provisional(spec: SlideSpec, text: str) -> Optional[SlideSpec]:
    """Show (or update in place) one provisional item on a list-like slide. None if the slide has no place."""
    pid = PROVISIONAL_PREFIX + spec.id
    pb = _find(spec, "points")
    if pb is not None:
        if sum(1 for i in pb.items if not i.provisional) >= CAPACITY["points"]:
            return None
        items = [i for i in pb.items if not i.provisional] + [Item(id=pid, text=text, provisional=True)]
        cand = _replace_block(spec, pb, pb.model_copy(update={"items": items}))
        return cand if fits(cand) else None
    db = _find(spec, "definition")
    if db is not None and len(spec.blocks) == 1:
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
