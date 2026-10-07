"""Summary and key-concepts slides (F-010): made when the teacher asks, shown on the projector like any slide.

- topic summary: one slide, the topic's 3-5 points (key_points)
- lecture summary: each topic a card with its points (groups, style list), at most 3 cards per slide
- key concepts: term tiles (facts, style terms), at most 6 per slide
More than fits on one slide → parts I, II … like the lecture's own slides.
"""
from __future__ import annotations

import math
from typing import Sequence

from copilot.materials.writer import Concept
from copilot.presentation.spec import Fact, FactsBlock, Group, GroupsBlock, Item, PointsBlock, SlideSpec

TOPICS_PER_SLIDE = 3
TERMS_PER_SLIDE = 6


def _balanced(items: Sequence, per: int) -> list[list]:
    """Split into the fewest slides of at most `per`, as even as possible (4 → 2 + 2, 7 → 3 + 2 + 2)."""
    if not items:
        return []
    n = math.ceil(len(items) / per)
    size, extra = divmod(len(items), n)
    out, i = [], 0
    for k in range(n):
        j = i + size + (1 if k < extra else 0)
        out.append(list(items[i:j]))
        i = j
    return out


def _parts(specs: list[SlideSpec]) -> list[SlideSpec]:
    if len(specs) < 2:
        return specs
    return [s.model_copy(update={"part": n, "continuation_of": specs[n - 2].id if n > 1 else None})
            for n, s in enumerate(specs, start=1)]


def topic_summary_slide(topic: str, points: Sequence[str]) -> SlideSpec:
    return SlideSpec(title="Summary", subtitle=topic, facet="Summary", layout="key_points", origin="materials",
                     blocks=[PointsBlock(items=[Item(text=p) for p in points])])


def lecture_summary_slides(title: str, topics: Sequence[tuple[str, Sequence[str]]]) -> list[SlideSpec]:
    return _parts([SlideSpec(title="Lecture summary", subtitle=title, facet="Summary", layout="groups",
                             origin="materials",
                             blocks=[GroupsBlock(style="list", groups=[
                                 Group(label=name, items=[Item(text=p) for p in points]) for name, points in chunk])])
                   for chunk in _balanced(list(topics), TOPICS_PER_SLIDE)])


def key_concepts_slides(title: str, concepts: Sequence[Concept]) -> list[SlideSpec]:
    return _parts([SlideSpec(title="Key concepts", subtitle=title, facet="Key concepts", layout="facts",
                             origin="materials",
                             blocks=[FactsBlock(style="terms", facts=[Fact(label=c.term, value=c.meaning)
                                                                      for c in chunk])])
                   for chunk in _balanced(list(concepts), TERMS_PER_SLIDE)])
