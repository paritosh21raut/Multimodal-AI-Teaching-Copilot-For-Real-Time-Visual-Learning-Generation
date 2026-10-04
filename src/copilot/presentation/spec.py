"""SlideSpec: the only thing the display renders. Contract: docs/contracts/slide-spec.md."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from copilot.core.events import new_id

Layout = Literal[
    "title", "concept", "definition", "key_points", "process_flow", "comparison", "timeline",
    "hierarchy", "cause_effect", "formula", "example", "application", "narrative",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Item(_Model):
    id: str = Field(default_factory=new_id)
    text: str
    emphasis: bool = False
    provisional: bool = False  # fast-path placeholder; replaced in place by refined content
    added: bool = False  # supporting content not said by the teacher (styled subtly)


class Step(_Model):
    id: str = Field(default_factory=new_id)
    label: str
    detail: str = ""


class Column(_Model):
    id: str = Field(default_factory=new_id)
    heading: str


class Row(_Model):
    id: str = Field(default_factory=new_id)
    aspect: str
    cells: list[str]


class TimelineEvent(_Model):
    id: str = Field(default_factory=new_id)
    when: str
    label: str
    detail: str = ""


class TreeNode(_Model):
    id: str = Field(default_factory=new_id)
    label: str
    children: list["TreeNode"] = Field(default_factory=list)


class CauseLink(_Model):
    id: str = Field(default_factory=new_id)
    cause: str
    effect: str


class Variable(_Model):
    symbol: str
    meaning: str
    unit: str = ""


class DefinitionBlock(_Model):
    type: Literal["definition"] = "definition"
    id: str = Field(default_factory=new_id)
    term: str
    definition: str
    notes: list[Item] = Field(default_factory=list)


class PointsBlock(_Model):
    type: Literal["points"] = "points"
    id: str = Field(default_factory=new_id)
    heading: str = ""
    items: list[Item] = Field(default_factory=list)


class ProcessBlock(_Model):
    type: Literal["process"] = "process"
    id: str = Field(default_factory=new_id)
    steps: list[Step] = Field(default_factory=list)
    cyclic: bool = False


class ComparisonBlock(_Model):
    type: Literal["comparison"] = "comparison"
    id: str = Field(default_factory=new_id)
    columns: list[Column]
    rows: list[Row] = Field(default_factory=list)

    @model_validator(mode="after")
    def _cells_match_columns(self) -> "ComparisonBlock":
        for r in self.rows:
            if len(r.cells) != len(self.columns):
                raise ValueError(f"row {r.aspect!r} has {len(r.cells)} cells for {len(self.columns)} columns")
        return self


class TimelineBlock(_Model):
    type: Literal["timeline"] = "timeline"
    id: str = Field(default_factory=new_id)
    events: list[TimelineEvent] = Field(default_factory=list)


class HierarchyBlock(_Model):
    type: Literal["hierarchy"] = "hierarchy"
    id: str = Field(default_factory=new_id)
    root: TreeNode


class CauseEffectBlock(_Model):
    type: Literal["cause_effect"] = "cause_effect"
    id: str = Field(default_factory=new_id)
    links: list[CauseLink] = Field(default_factory=list)


class FormulaBlock(_Model):
    type: Literal["formula"] = "formula"
    id: str = Field(default_factory=new_id)
    latex: str
    spoken: str = ""  # plain-language form as the teacher said it
    variables: list[Variable] = Field(default_factory=list)


class ExampleBlock(_Model):
    type: Literal["example"] = "example"
    id: str = Field(default_factory=new_id)
    title: str = ""
    text: str


class CalloutBlock(_Model):
    type: Literal["callout"] = "callout"
    id: str = Field(default_factory=new_id)
    kind: Literal["note", "tip", "key"] = "key"
    text: str


class ImageBlock(_Model):
    type: Literal["image"] = "image"
    id: str = Field(default_factory=new_id)
    url: str
    alt: str
    credit: str = ""
    licence: str = ""


Block = Annotated[
    Union[
        DefinitionBlock, PointsBlock, ProcessBlock, ComparisonBlock, TimelineBlock, HierarchyBlock,
        CauseEffectBlock, FormulaBlock, ExampleBlock, CalloutBlock, ImageBlock,
    ],
    Field(discriminator="type"),
]


class SlideSpec(_Model):
    id: str = Field(default_factory=new_id)
    version: int = 0
    topic_id: str = ""
    subtopic_id: Optional[str] = None
    facet: Optional[str] = None  # e.g. "Process", "Factors"
    title: str
    subtitle: str = ""
    continuation_of: Optional[str] = None  # previous slide of the same concept
    layout: Layout = "concept"
    blocks: list[Block] = Field(default_factory=list)
    language: str = "en"

    @model_validator(mode="after")
    def _unique_block_ids(self) -> "SlideSpec":
        ids = [b.id for b in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("block ids must be unique within a slide")
        return self
