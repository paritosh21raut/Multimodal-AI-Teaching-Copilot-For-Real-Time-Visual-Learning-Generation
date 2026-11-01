"""StoryboardSpec (V3 ST1, docs/v3/ST1-story-core.md): what the story slide shows. Built only from said words and
found pictures; the display (web/story/player.js) draws it, the camera motion is the display's.

    cast     the people / things of the story (a said name or noun, its picture), kept for the whole story
    scenes   one per story beat: its caption (said words, shortened), its picture, who stands in it, its bubbles
    look     ST2: each cast member's own colour and figure; gender only from said words
    shown    the scene on screen (a newer scene waits for the dwell time; the teacher's Prev / Next moves it)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from copilot.core.events import new_id

Camera = Literal["zoom_in", "zoom_out", "pan_left", "pan_right"]
CAMERAS: tuple[Camera, ...] = ("zoom_in", "pan_right", "zoom_out", "pan_left")
SpeechKind = Literal["say", "ask", "shout", "whisper", "reply"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CastMember(_Model):
    id: str
    name: str                 # as said: "Ravi", "a young clerk", "a drop of water"
    noun: str = ""            # its picture's noun ("clerk", "person", "droplet")
    picture: str = ""         # /scene-pic/<slug>.png ("" = its initial in a circle)
    gender: Literal["", "he", "she"] = ""   # ST2: only from said words (a noun, a pronoun with one person meant)
    look: int = 0             # ST2: its colour (0..5, in cast order): two people never look the same


class Bubble(_Model):
    id: str = Field(default_factory=new_id)
    speaker: str              # a cast id
    text: str                 # the said words only
    kind: SpeechKind = "say"
    to: str = ""              # the cast id spoken to ("" = not said)


class StoryScene(_Model):
    id: str = Field(default_factory=new_id)
    caption: str = ""         # the newest narrative line of the beat, shortened (said words only)
    lines: list[str] = Field(default_factory=list)  # the narrative lines of the beat (the dialogue is in bubbles)
    when: str = ""            # said: "1905", "years later"
    where: str = ""           # said: "Bern", "the clouds"
    cast: list[str] = Field(default_factory=list)   # cast ids standing in the scene, in order of appearance
    query: str = ""           # the picture search (said words)
    image: str = ""           # /media/<id>.jpg once found
    image_alt: str = ""
    credit: str = ""          # source · licence · author of the image
    emoji: str = ""           # /scene-pic/<slug>.png of the beat's noun: at once, and when no image is found
    camera: Camera = "zoom_in"
    bubbles: list[Bubble] = Field(default_factory=list)


class StoryboardSpec(_Model):
    title: str = "Story"
    cast: list[CastMember] = Field(default_factory=list)
    scenes: list[StoryScene] = Field(default_factory=list)
    shown: int = 0
    version: int = 0

    def member(self, cid: str) -> CastMember | None:
        return next((c for c in self.cast if c.id == cid), None)
