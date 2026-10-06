"""Interpretation contract: the validated output of one LLM interpretation call.

Lives in core so events and the state store are typed without importing the understanding package.
Line numbers refer to the numbered transcript lines of the request (1-based); `segment_ids` maps them back.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Relation = Literal[
    "same_concept", "elaboration", "sub_concept", "sibling_concept", "new_topic", "digression",
]
ActKind = Literal[
    "definition", "explanation", "process", "comparison", "example", "formula", "cause_effect",
    "timeline", "classification", "application", "question", "recap", "transition", "other",
]
Representation = Literal[
    "definition", "concept", "key_points", "process_flow", "comparison", "timeline", "hierarchy",
    "cause_effect", "formula", "example", "application", "narrative", "none",
]


class _Lenient(BaseModel):
    # LLMs add stray keys; ignore them rather than failing the whole interpretation.
    model_config = ConfigDict(extra="ignore", frozen=True)


class Pair(_Lenient):
    aspect: str = ""
    left: str = ""
    right: str = ""


class TimedEvent(_Lenient):
    when: str = ""
    what: str


class Variable(_Lenient):
    symbol: str
    meaning: str = ""


class Formula(_Lenient):
    expression: str
    variables: list[Variable] = Field(default_factory=list)


class CauseEffect(_Lenient):
    cause: str
    effect: str


class Fact(_Lenient):
    """A short attribute fact about a named thing: label "Smallest planet", value "Mercury"."""
    label: str
    value: str = ""


class Group(_Lenient):
    """A named group in a classification: label "Inner planets", items ["Mercury", "Venus", ...]."""
    label: str
    items: list[str] = Field(default_factory=list)


class ContentItems(_Lenient):
    term: str = ""
    definition: str = ""
    points: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    compare: list[str] = Field(default_factory=list)  # the things compared, e.g. ["photosynthesis", "respiration"]
    pairs: list[Pair] = Field(default_factory=list)
    events: list[TimedEvent] = Field(default_factory=list)
    formula: Optional[Formula] = None
    causes: list[CauseEffect] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    label: str = ""  # what a classification classifies ("Branches of chemistry"); heading of a list
    facts: list[Fact] = Field(default_factory=list)
    groups: list[Group] = Field(default_factory=list)


class DiscourseAct(_Lenient):
    act: ActKind
    lines: list[int] = Field(default_factory=list)
    items: ContentItems = Field(default_factory=ContentItems)
    added: bool = False  # small clarifying addition not said by the teacher


ConcernKind = Literal["factual", "transcription"]


class ConcernItem(_Lenient):
    claim: str
    issue: str
    suggested_correction: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    lines: list[int] = Field(default_factory=list)
    # factual: the statement looks wrong; transcription: a word/formula looks mis-heard or mis-spoken.
    # Acts carry the CORRECTED content; claim = what the teacher said, suggested_correction = the correct form.
    kind: ConcernKind = "factual"
    wrong: str = ""   # the minimal words as the teacher said them ("Neptune", "Omo atomic")
    right: str = ""   # the words now in the acts instead ("Uranus", "monoatomic")

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v: object) -> object:
        return v if v in ("factual", "transcription") else "factual"


class Revision(_Lenient):
    """Rewrite of a CURRENT SLIDE item (ref "S3") that the NEW lines complete or correct."""
    ref: str
    text: str


class VisualHint(_Lenient):
    """The model's suggestion that a picture helps (F-007b): a concrete thing (photo) or a process/structure
    (diagram). Only a hint — presentation's image policy decides."""
    query: str = ""
    kind: Literal["photo", "diagram"] = "photo"

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v: object) -> object:
        return v if v in ("photo", "diagram") else "photo"

    @field_validator("query")
    @classmethod
    def _query(cls, v: str) -> str:
        return " ".join(v.split())[:60]


class Interpretation(_Lenient):
    topic: str
    subtopic: str = ""
    relation: Relation
    acts: list[DiscourseAct] = Field(default_factory=list)
    representation_hint: Representation = "none"
    meta_lines: list[int] = Field(default_factory=list)
    concerns: list[ConcernItem] = Field(default_factory=list)
    revisions: list[Revision] = Field(default_factory=list)
    level_estimate: str = ""
    subject_estimate: str = ""
    summary_delta: str = ""
    visual: Optional[VisualHint] = None

    @field_validator("visual", mode="before")
    @classmethod
    def _visual(cls, v: object) -> object:
        # models write {} / {"query": ""} / "none" / a bare string for "no picture": all mean None
        if isinstance(v, str):
            return {"query": v} if v.strip() and v.strip().lower() not in ("none", "null", "no") else None
        if isinstance(v, dict) and not str(v.get("query") or "").strip():
            return None
        return v

    @field_validator("topic")
    @classmethod
    def _topic_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must not be blank")
        return v.strip()

    @field_validator("subtopic", "summary_delta", "level_estimate", "subject_estimate")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()
