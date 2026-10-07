"""Metadata filters and priors for image candidates (F-007b). Pure.

Rejects what can never be a good classroom image (logos, flags, stamps, maps, non-English diagrams, unfree or
restricted files, tiny or extreme aspect ratios, Wikipedia articles about films/novels/bands ...). The prior is a
small bonus for signals of quality and fit (the topic's Wikipedia lead image, featured pictures, English labels,
diagram words for a diagram request); CLIP decides relevance.
"""
from __future__ import annotations

import re
from typing import Optional

from copilot.visuals.sources import Candidate

MIMES = {"image/jpeg", "image/png", "image/svg+xml", "image/webp", "image/tiff"}
MIN_SIDE_PX = 400       # longest side of a raster original
MIN_SHORT_PX = 250
ASPECT = (0.5, 2.2)     # width / height
DIAGRAM_MAX_ASPECT = 2.5  # a diagram may be wider ("Covalent bond hydrogen.svg", 2.33; long test 2026-10-06)
_BLOCK = re.compile(
    r"\b(?:logo|logos|flag|flags|coat of arms|emblem|seal of|stamp|stamps|postage|banner|icon|icons|signature|"
    r"wordmark|screenshot|album cover|book cover|poster|map|maps|locator|coin|coins|banknote|tattoo|cake|"
    r"costume|toy|statue|sculpture|carving|graffiti|meme|cartoon|caricature|advertisement|"
    # not for a classroom projector: medical pathology and gore
    r"autopsy|cadaver|corpse|surgery|surgical|cancer|tumou?r|wound|injury|disease|lesion|necrosis)\b",
    re.IGNORECASE)
_NOT_TOPIC = re.compile(
    r"\b(?:film|movie|novel|album|song|single|band|tv|television|series|episode|video game|book|magazine|"
    r"newspaper|company|brand|footballer|singer|actor|actress|rapper|politician|ship|horse|racehorse|play|"
    r"opera|musical|sculpture|painting|restaurant|software)\b", re.IGNORECASE)
# "Heart diagram-fa.svg", "Diagram el.svg", "Cell (de).png", "Cycle_zh-hans.svg": a 2-letter code after a separator,
# or a 3-letter / regional code only after "-" or "_" ("The Sun.jpg" is not Sundanese)
_LANG_CODE = re.compile(r"(?:[-_ (]([a-z]{2}(?:-[a-z]+)?)|[-_]([a-z]{3}))\)?\.(?:svg|png|jpe?g|gif|webp|tiff?)$",
                        re.IGNORECASE)
_LANG3 = {"ast", "fil", "yue", "hsb", "dsb", "ckb", "nds", "bar", "vec", "scn", "arz", "azb", "pnb", "mzn", "tgl",
          "fas", "deu", "ger", "fra", "fre", "spa", "rus", "zho", "chi", "jpn", "kor", "ara", "hin", "ben", "por",
          "ita", "nld", "pol", "tur", "ukr", "heb", "srp", "hrv", "ces", "cze", "swe", "fin", "ell", "gre"}
_FOREIGN_LANG_CAT =re.compile(r"\b(\w+)-language\b", re.IGNORECASE)
_IN_LANGUAGE = re.compile(r"\bin[ _]([A-Za-z]+)[ _]language\b", re.IGNORECASE)
_NOT_LANG = {"en", "en-us", "en-gb", "eng", "hd", "bw", "lr", "hr", "v2", "v3", "of", "in", "on", "at", "to",
             "is", "it", "an", "as", "by", "up", "my", "me", "we", "us", "go", "no", "or", "so", "do", "ii", "iv",
             "big", "old", "new", "map", "rgb", "alt", "fig", "cut", "top", "red", "low", "pic", "img", "ani",
             "the", "and", "art", "svg", "png", "jpg", "sun", "day", "two", "one", "mod", "fix", "cropped"}
_FREE = re.compile(r"\b(?:cc|public domain|pd|gfdl|cc0|attribution|no restrictions)\b", re.IGNORECASE)
_QUALITY = re.compile(r"\b(?:featured pictures|featured diagrams|quality images|valued images)\b", re.IGNORECASE)
_DIAGRAMMY = re.compile(r"\b(?:diagram|diagrams|labell?ed|schematic|illustration|anatomy|cross[- ]section|"
                        r"cycle|process)\b", re.IGNORECASE)


def _haystack(c: Candidate) -> str:
    name = re.sub(r"^File:", "", c.title)
    return f"{name} | {c.categories} | {c.description}"


# Labelled diagrams first (F-009 §3, user 2026-10-07): "prefer labelled diagrams and images from Wikipedia; if none,
# show one without labels" — only where labels help (a structure, organ, system, cycle, apparatus), not for photos
# of planets or animals.
_LABELLED = re.compile(r"(?:\b|_)(?:labell?ed|annotated|with[ _](?:english[ _])?labels|labels[ _]in[ _]english|"
                       r"label[ _]diagram)(?:\b|_)", re.IGNORECASE)
_STRUCTURE = re.compile(
    r"\b(?:systems?|organs?|cells?|structures?|parts?|anatomy|cycles?|apparatus|layers?|cross[- ]sections?|"
    r"heart|eye|ear|brain|kidneys?|lungs?|liver|stomach|intestines?|skeleton|skull|teeth|tooth|bones?|"
    r"muscles?|skin|neurons?|tissues?|flower|leaf|leaves|roots?|stem|seed|stomata|chloroplasts?|mitochondri\w*|"
    r"nucleus|bacteri\w*|virus|microscope|circuit|engine|motor|generator|transformer|volcano|atom)\b",
    re.IGNORECASE)


def is_labelled(c: Candidate) -> bool:
    """Says it has labels, or carries English labels ("Heart diagram-en.svg", "English-language diagrams")."""
    return bool(_LABELLED.search(_haystack(c))) or language(c) == "en"


def wants_labels(query: str, kind: str) -> bool:
    """A subject where a labelled diagram teaches more than a plain picture."""
    return kind == "diagram" or bool(_STRUCTURE.search(query))


_GENERIC = {"human", "diagram", "photo", "picture", "image", "structure", "labelled", "labeled", "the", "of", "and",
            "with", "for", "its", "parts", "simple", "basic", "types", "structures", "diagrams", "graph", "chart",
            "illustration", "schematic", "drawing", "formation"}


def key_words(query: str) -> list[str]:
    """Distinctive query words ("leaf stomata" → leaf, stomata; "human heart" → heart)."""
    return [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 3 and w not in _GENERIC]


def core_query(query: str) -> str:
    """The thing a long query is about: its first two distinctive words in their spoken form ("sigma bond orbital
    overlap" → "sigma bond", "Charles Law graph" → "Charles Law"); "" when the query is that short already. Commons
    search is literal: the long phrase found 1-4 files in the long test 2026-10-06."""
    words = re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?", query)
    content = [w for w in words if len(w) >= 2 and w.lower() not in _GENERIC]
    pictorial = any(w.lower() in _PICTURE_WORDS for w in words)
    if len(content) > 2 or (pictorial and content):
        return " ".join(content[:2])
    return ""


_PICTURE_WORDS = {"diagram", "diagrams", "photo", "picture", "image", "graph", "chart", "illustration", "schematic",
                  "drawing", "structure", "structures", "formation", "labelled", "labeled"}


def _stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w  # stomata ~ stomate, molecules ~ molecule


def mentions_query(c: Candidate, query: str) -> bool:
    """The distinctive query words appear in the file name, categories or description (or the article title): all of
    one or two ("Rock cycle" is not about "water cycle", "Lisc lipy.jpg" is not about "leaf stomata"), most of three
    or more ("Bond lengths in water.png" for "covalent bond length"; CLIP judges the picture)."""
    hay = re.sub(r"[^a-z0-9]+", " ", f"{_haystack(c)} {c.article}".lower())
    squashed = hay.replace(" ", "")  # "WaterCycle"
    words = key_words(query)
    found = sum(1 for w in words if _stem(w) in hay or _stem(w) in squashed)
    return found == len(words) if len(words) <= 2 else found * 2 >= len(words) + (len(words) % 2)


def _names_query(c: Candidate, query: str) -> bool:
    """At least one distinctive query word in the file name itself."""
    name = re.sub(r"[^a-z0-9]+", " ", re.sub(r"^file:", "", c.title.lower()))
    squashed = name.replace(" ", "")
    return any(_stem(w) in name or _stem(w) in squashed for w in key_words(query))


def is_topic_lead(c: Candidate, query: str) -> bool:
    """The lead image of the Wikipedia article that IS the topic ("Sun" → article "Sun")."""
    if c.source != "wikipedia" or not c.article:
        return False
    title = set(re.findall(r"[a-z0-9]+", c.article.lower())) - _GENERIC
    words = set(key_words(query))
    return bool(words) and (title <= words or words <= title)


def language(c: Candidate) -> str:
    """"en", "" (none detected) or the foreign label language ("fa", "Persian")."""
    m = _LANG_CODE.search(c.title)
    code = (m.group(1) or m.group(2)).lower() if m else ""
    if m and m.group(2) and code not in _LANG3:  # "X-ray.jpg", "Sun-dog.jpg": a word, not a language
        code = ""
    if code in ("en", "en-us", "en-gb", "eng"):
        return "en"
    if code and code not in _NOT_LANG:
        return code
    # "Parts of a flower in kashmiri language.jpg" (labelled-diagram search, 2026-10-07)
    named = _IN_LANGUAGE.search(f"{c.title} {c.description[:120]}")
    if named and named.group(1).lower() != "english":
        return named.group(1).lower()
    cats = [x.lower() for x in _FOREIGN_LANG_CAT.findall(c.categories)]
    if cats and "english" not in cats:
        return cats[0]
    return "en" if "english" in cats else ""


def reject_reason(c: Candidate, query: str = "", kind: str = "photo") -> Optional[str]:
    """Why a candidate can never be shown, or None."""
    if c.mime.lower() not in MIMES:
        return f"mime {c.mime or '?'}"
    if c.mime != "image/svg+xml" and c.width and c.height:
        if max(c.width, c.height) < MIN_SIDE_PX or min(c.width, c.height) < MIN_SHORT_PX:
            return f"small {c.width}x{c.height}"
    if c.width and c.height and not ASPECT[0] <= c.width / c.height <= (
            DIAGRAM_MAX_ASPECT if kind == "diagram" else ASPECT[1]):
        return f"aspect {c.width / c.height:.2f}"
    if c.source != "openverse" and not _FREE.search(c.licence):
        return f"licence {c.licence or '?'}"
    if c.meta.get("restrictions"):
        return f"restricted ({c.meta['restrictions']})"
    q = query.lower()
    hay = _haystack(c)
    if c.source == "openverse":
        hay = f"{c.title} | {c.categories}"
    blocked = [m.group(0).lower() for m in _BLOCK.finditer(hay) if m.group(0).lower() not in q]
    if blocked:
        return f"blocked word {blocked[0]!r}"
    lang = language(c)
    if lang not in ("", "en"):
        return f"labels in {lang}"
    if c.article_description and _NOT_TOPIC.search(c.article_description) and not _NOT_TOPIC.search(q):
        return f"article is a {c.article_description!r}"
    if not mentions_query(c, query):
        return "query words missing"
    if kind == "diagram" and not _names_query(c, query):
        # a diagram's labels are in the file name's language: "Metamorfosis Katak.png" has Indonesian labels
        return "file name not in English"
    return None


def prior(c: Candidate, query: str, kind: str) -> float:
    """Small bonus (≤ ~0.03) added to the CLIP similarity for ranking among accepted candidates."""
    bonus = 0.0
    if is_topic_lead(c, query):
        bonus += 0.03  # editors chose it to illustrate exactly this topic
    elif c.source == "wikipedia" and c.rank == 0:
        bonus += 0.01
    if _QUALITY.search(c.categories):
        bonus += 0.01
    if language(c) == "en":
        bonus += 0.005
    if kind == "diagram" and _DIAGRAMMY.search(_haystack(c)):
        bonus += 0.01
    return bonus
