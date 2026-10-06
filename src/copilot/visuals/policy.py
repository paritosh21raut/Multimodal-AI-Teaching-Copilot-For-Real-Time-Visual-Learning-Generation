"""Image policy (F-007b): deterministic, pure. Does this slide get an image, and which?

The model's `visual` hint says a picture would help (concrete thing → photo, process/structure → diagram); this
policy decides. Need, not quota (user 2026-10-06): solar system, organs, apparatus — yes; kinetic-energy equations —
no. When unsure: no image.

Never: title slides, slides without teacher content yet, slides with a full-width diagram (process flow,
comparison, timeline, cause-effect, formula, tree) or groups, more than 4 fact tiles, two definitions side by side
(concept columns), an abstract query ("energy", "velocity"), a frame where the teacher removed the image.
A later part of the same frame keeps the frame's image while the content is still about it (no new hint), gets a
new one when the hint names something else, and none when its content is abstract (user answer 3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from copilot.core.interpretation import VisualHint
from copilot.presentation.composer import teacher_items
from copilot.presentation.spec import ImageBlock, SlideSpec

NO_IMAGE_BESIDE = {"process", "comparison", "timeline", "cause_effect", "formula", "hierarchy", "groups"}
MAX_FACT_TILES = 4
# words that name ideas, not things: a picture search for them returns noise
_ABSTRACT = {"energy", "force", "forces", "velocity", "speed", "acceleration", "motion", "work", "power", "momentum",
             "equation", "equations", "formula", "formulas", "law", "laws", "theory", "concept", "definition",
             "kinetic", "potential", "kinematics", "displacement", "distance", "time", "mass", "quantity",
             "quantities", "unit", "units", "value", "number", "numbers", "property", "properties", "type", "types",
             "example", "examples", "importance", "meaning", "introduction", "overview", "summary", "factors",
             "reaction", "neutralization", "quadratic", "roots", "function", "variable", "solution", "solutions",
             "current", "voltage", "resistance", "charge", "matter", "chemistry", "physics", "biology", "science"}


# words about the picture, not its subject ("speed and velocity diagram" is as abstract as "speed and velocity")
_FILLER = {"of", "the", "and", "a", "an", "in", "vs", "versus", "diagram", "diagrams", "photo", "photos", "image",
           "images", "picture", "pictures", "illustration", "chart"}


def is_abstract(query: str) -> bool:
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in _FILLER]
    return not words or all(w in _ABSTRACT for w in words)


def norm_query(query: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", query.lower()))


@dataclass
class FrameVisual:
    """What the engine remembers per frame (topic > facet)."""
    hint: Optional[VisualHint] = None      # the model's latest hint for this frame (it may arrive before the slide)
    query: str = ""
    kind: str = "photo"
    image: Optional[ImageBlock] = None     # the frame's current image (carried to later parts)
    candidates: list[ImageBlock] = field(default_factory=list)  # accepted alternatives for Change image
    shown_ids: set[str] = field(default_factory=set)   # image ids already offered (Change image skips them)
    removed: bool = False                  # the teacher removed the image: this frame gets none automatically
    no_match: set[str] = field(default_factory=set)    # queries that found nothing relevant
    pending: str = ""                      # query of the running search
    retry_at: float = 0.0                  # lecture time before which a failed search is not repeated


@dataclass
class Decision:
    action: Literal["none", "search", "keep"]
    reason: str
    query: str = ""
    kind: str = "photo"


def blocked(spec: SlideSpec) -> Optional[str]:
    """Why this slide can never take an automatic image (None = it can)."""
    if spec.layout == "title":
        return "title slide"
    if teacher_items(spec) == 0:
        return "no content yet"
    for b in spec.blocks:
        if b.type in NO_IMAGE_BESIDE:
            return f"{b.type} needs the full width"
        if b.type == "facts" and len(b.facts) > MAX_FACT_TILES:
            return f"{len(b.facts)} fact tiles"
    if sum(1 for b in spec.blocks if b.type == "definition") > 1:
        return "two concepts side by side"
    return None


def decide(spec: SlideSpec, hint: Optional[VisualHint], frame: FrameVisual) -> Decision:
    """Called after content was placed on `spec` (the slide the unit's content went to)."""
    if any(b.type == "image" for b in spec.blocks):
        return Decision("none", "has an image")
    if frame.removed:
        return Decision("none", "teacher removed this topic's image")
    why = blocked(spec)
    if why:
        return Decision("none", why)
    if hint is not None and hint.query:
        q = norm_query(hint.query)
        if is_abstract(hint.query):
            return Decision("none", f"abstract query {hint.query!r}")
        if q in frame.no_match:
            return Decision("none", f"nothing relevant found for {hint.query!r} before")
        if frame.image is not None and q == norm_query(frame.query):
            return Decision("keep", "same visual as this topic's image", frame.query, frame.kind)
        if q == norm_query(frame.pending):
            return Decision("none", "search running")
        return Decision("search", "model hint", hint.query, hint.kind)
    if frame.image is not None:  # a later part, still about the same thing
        return Decision("keep", "next part of a topic with an image", frame.query, frame.kind)
    return Decision("none", "no visual hint")
