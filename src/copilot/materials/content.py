"""What was taught, per topic (F-010): the lecture's slides as readable lines + the transcript of each subtopic.

A topic is the slides' topic name (the crumb on the slide, as in the /control structure tree); a subtopic is a slide
title inside it (the parts of one frame merge). A transcript line belongs to the subtopic of the first content slide
that changed after it was said (the interpretation lands on a slide a few seconds after the words), or the last one.
Everything handed to the LLM goes through `budgeted`, so a prompt never exceeds its budget, whatever the lecture.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from copilot.core.textutil import approx_tokens
from copilot.materials.archive import LectureRecord, topic_name


@dataclass
class Subtopic:
    key: str                       # "L1.T2.S3": lecture, topic, subtopic (the LLM answers with it)
    topic: str
    title: str
    slides: list[dict[str, Any]] = field(default_factory=list)
    said: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out: list[str] = []
        for s in self.slides:
            for b in s.get("blocks") or []:
                for line in block_lines(b):
                    if line not in out:
                        out.append(line)
        return out


@dataclass
class Topic:
    name: str
    subtopics: list[Subtopic] = field(default_factory=list)


@dataclass
class Lecture:
    """One lecture's taught content, in the order it was taught."""
    id: str
    title: str
    date: str
    topics: list[Topic] = field(default_factory=list)

    @property
    def subtopics(self) -> list[Subtopic]:
        return [s for t in self.topics for s in t.subtopics]


def _tree(node: dict[str, Any], depth: int = 0) -> list[str]:
    out = [("  " * depth) + "- " + node.get("label", "")]
    for c in node.get("children") or []:
        out += _tree(c, depth + 1)
    return out


def block_lines(b: dict[str, Any]) -> list[str]:
    """A slide block as plain lines (what a student would read on the slide)."""
    t = b.get("type")
    if t == "definition":
        return [f"{b['term']}: {b['definition']}"] + [f"- {n['text']}" for n in b.get("notes") or []]
    if t == "points":
        head = [b["heading"] + ":"] if b.get("heading") else []
        return head + [f"- {i['text']}" for i in b.get("items") or []]
    if t == "process":
        start = b.get("start") or 1
        return [f"{start + n}. {s['label']}" + (f" - {s['detail']}" if s.get("detail") else "")
                for n, s in enumerate(b.get("steps") or [])] + (["(a cycle)"] if b.get("cyclic") else [])
    if t == "comparison":
        cols = [c["heading"] for c in b.get("columns") or []]
        return [f"Comparison of {' vs '.join(cols)}:"] + [
            f"- {r['aspect']}: " + " | ".join(f"{c}: {v}" for c, v in zip(cols, r.get("cells") or []))
            for r in b.get("rows") or []]
    if t == "timeline":
        return [f"- {e['when']}: {e['label']}" + (f" - {e['detail']}" if e.get("detail") else "")
                for e in b.get("events") or []]
    if t == "hierarchy":
        return _tree(b["root"])
    if t == "cause_effect":
        return [f"- {l['cause']} -> {l['effect']}" for l in b.get("links") or []]
    if t == "formula":
        line = "Formula: " + (b.get("spoken") or b.get("latex") or "")
        vars_ = [f"{v['symbol']} = {v['meaning']}" + (f" ({v['unit']})" if v.get("unit") else "")
                 for v in b.get("variables") or []]
        return [line] + ([f"  where {', '.join(vars_)}"] if vars_ else [])
    if t == "example":
        return [f"Example{': ' + b['title'] if b.get('title') else ''}: {b['text']}"]
    if t == "callout":
        return [f"Note: {b['text']}"]
    if t == "facts":
        head = [b["heading"] + ":"] if b.get("heading") else []
        return head + [f"- {f['label']}: {f['value']}" if f.get("value") else f"- {f['label']}"
                       for f in b.get("facts") or []]
    if t == "groups":
        head = [b["heading"] + ":"] if b.get("heading") else []
        return head + [f"- {g['label']}: " + "; ".join(i["text"] for i in g.get("items") or [])
                       for g in b.get("groups") or []]
    if t == "image":
        return [f"[Picture: {b.get('alt', '')}]"]
    return []


ASSIGN_WINDOW_S = 40.0  # a line's slide is patched within this long after it was said (interpretation lag)
_STOP = set("this that with from have were what which when then there their they them these those about into also "
            "will would could should been being here very more most some such than only just like each other".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 4 and w not in _STOP}


def block_lines_of(spec: dict[str, Any]) -> list[str]:
    return [spec.get("title", "")] + [line for b in spec.get("blocks") or [] for line in block_lines(b)]


def lecture_content(rec: LectureRecord, number: int = 1) -> Lecture:
    """The record's content slides grouped into topics → subtopics, each with its transcript lines."""
    topics: dict[str, Topic] = {}
    subs: dict[tuple[str, str], Subtopic] = {}
    owner: dict[str, Subtopic] = {}  # slide id -> its subtopic
    for s in rec.content_slides:
        name = topic_name(s).strip() or rec.title
        topic = topics.setdefault(name.lower(), Topic(name))
        title = (s.get("title") or name).strip()
        key = (name.lower(), title.lower())
        sub = subs.get(key)
        if sub is None:
            sub = subs[key] = Subtopic(f"L{number}.T{list(topics).index(name.lower()) + 1}"
                                       f".S{len(topic.subtopics) + 1}", name, title)
            topic.subtopics.append(sub)
        sub.slides.append(s)
        owner[s["id"]] = sub
    patches = [(ts, sid) for ts, sid in rec.patches if sid in owner]
    times = [ts for ts, _ in patches]
    words = {sid: _words(" ".join(block_lines_of(s))) for sid, s in ((s["id"], s) for s in rec.content_slides)}
    for line in rec.transcript:
        text = line.get("text", "").strip()
        if not patches or not text:
            continue
        i = bisect.bisect_left(times, line["ts"])
        # the slides that changed soon after the words were said; the one whose content shares the most words
        # with them (a slide still being refined is patched after the next topic's first words, long test 2026-10-06)
        window = list(dict.fromkeys(sid for ts, sid in patches[i:] if ts <= line["ts"] + ASSIGN_WINDOW_S))
        said = _words(text)
        best = max(window, key=lambda sid: len(said & words.get(sid, set())), default=None)
        if best is None or not said & words.get(best, set()):
            best = patches[min(i, len(patches) - 1)][1]
        owner[best].said.append(text)
    from datetime import datetime

    date = datetime.fromtimestamp(rec.started).strftime("%d %b %Y") if rec.started else ""
    return Lecture(rec.id, rec.title, date, list(topics.values()))


def topic_of(lecture: Lecture, slide: Optional[dict[str, Any]]) -> Optional[Topic]:
    """The topic a slide (the live one) belongs to; the last topic when the slide is the title or unknown."""
    if slide is not None and slide.get("layout") != "title":
        name = (topic_name(slide).strip() or lecture.title).lower()
        for t in lecture.topics:
            if t.name.lower() == name:
                return t
    return lecture.topics[-1] if lecture.topics else None


def _cut(lines: list[str], budget: int) -> list[str]:
    out, used = [], 0
    for line in lines:
        cost = approx_tokens(line) + 1
        if used + cost > budget:
            break
        out.append(line)
        used += cost
    return out


def budgeted(subtopics: Iterable[Subtopic], budget: int, said: bool = False, said_share: float = 0.45) -> str:
    """The subtopics' material within `budget` tokens: every subtopic gets a fair share (unused share passes on to
    the next), slide lines first, then (said=True) what the teacher said, up to `said_share` of its share."""
    subs = list(subtopics)
    parts: list[str] = []
    left = budget
    for n, sub in enumerate(subs):
        share = left // (len(subs) - n)
        head = f"[{sub.key}] {sub.topic} > {sub.title}"
        room = share - approx_tokens(head) - 1
        if room <= 0:
            break
        slide_room = room - (int(room * said_share) if said and sub.said else 0)
        body = _cut(sub.lines(), slide_room)
        text = "\n".join([head] + body)
        if said and sub.said:
            spoken = " ".join(sub.said)
            room_said = room - sum(approx_tokens(l) + 1 for l in body) - 4
            if room_said > 20:
                words = spoken.split()
                while words and approx_tokens(" ".join(words)) > room_said:
                    words = words[: int(len(words) * 0.85)]
                if words:
                    text += "\nTeacher said: " + " ".join(words)
        parts.append(text)
        left -= approx_tokens(text) + 1
    return "\n\n".join(parts)
