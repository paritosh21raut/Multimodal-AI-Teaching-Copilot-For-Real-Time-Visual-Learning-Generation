"""Display annotations derived from slide text (F-007a follow-up, user's live tests 2026-10-06).

Applied by the Deck to every spec it publishes, so every path (merge, revision, correction, teacher switch) gets it:
- `math`: the text with ``\\(latex\\)`` around its equations (`mathtext.mark_math`), so points, examples, steps and
  definitions show formulas, not "v = u + a·t" as plain text;
- `PointsBlock.style`: numbers only for a counted or ordered list (a labelled list of kinds, "First … / Then …",
  "1. …"), letters for "a) … b) …" options, bullets otherwise (explanations, a single point).
Pure; the text itself is never changed.
"""
from __future__ import annotations

import re

from copilot.presentation.mathtext import mark_math
from copilot.presentation.spec import Item, ListStyle, PointsBlock, SlideSpec, Step

_ORDINAL = re.compile(r"^(?:first(?:ly)?|second(?:ly)?|third(?:ly)?|fourth|fifth|next|then|finally|lastly|step\s*\d+|"
                      r"\d+[.)])\b", re.IGNORECASE)
_LETTER = re.compile(r"^\(?([a-h])[).]\s")


def list_style(block: PointsBlock) -> ListStyle:
    items = [i for i in block.items if not i.provisional]
    if len(items) < 2:
        return "bullets"
    letters = [_LETTER.match(i.text) for i in items]
    if all(letters) and [m.group(1) for m in letters if m] == [chr(ord("a") + k) for k in range(len(items))]:
        return "letters"
    ordered = sum(1 for i in items if _ORDINAL.match(i.text.strip()))
    if block.heading.strip() or ordered >= 2:
        return "numbers"
    return "bullets"


def _item(i: Item) -> Item:
    m = mark_math(i.text)
    return i if m == i.math else i.model_copy(update={"math": m})


def _step(s: Step) -> Step:
    m = mark_math(s.label)
    return s if m == s.math else s.model_copy(update={"math": m})


def annotate(spec: SlideSpec) -> SlideSpec:
    blocks = []
    for b in spec.blocks:
        if b.type == "points":
            b = b.model_copy(update={"items": [_item(i) for i in b.items]})
            b = b.model_copy(update={"style": list_style(b)})
        elif b.type == "definition":
            b = b.model_copy(update={"math": mark_math(b.definition), "notes": [_item(n) for n in b.notes]})
        elif b.type in ("example", "callout"):
            b = b.model_copy(update={"math": mark_math(b.text)})
        elif b.type == "process":
            b = b.model_copy(update={"steps": [_step(s) for s in b.steps]})
        elif b.type == "groups":
            b = b.model_copy(update={"groups": [g.model_copy(update={"items": [_item(i) for i in g.items]})
                                                for g in b.groups]})
        blocks.append(b)
    return spec.model_copy(update={"blocks": blocks})
