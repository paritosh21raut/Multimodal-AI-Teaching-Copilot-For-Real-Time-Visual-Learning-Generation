"""The stage fast path (F-017 §3, E3): one teacher line -> draft ops in < 50 ms, 0 tokens. The draft is drawn at once
(ghosted, `src: fast`) and the LLM delta of the same line replaces it (stage.log).

    nouns     catalog names and synonyms (n-grams up to 3 words, plurals), people nouns, ground / fluid words
    pronouns  he / she / they -> the last person said, it -> the last thing said (in this line, else the graph)
    verbs     a closed lexicon of inflected forms -> the contract's verbs (stage.ops), a few synonyms (shove = push)
    spatial   on / in / under / behind / next to ... between two nouns of the line
    prefetch  nouns after a determiner that the catalog does not know: the lookup ladder starts on them early

Never numbers, laws or givens: a stated number needs the LLM's quote (the validator checks it); the fast path only
says what is there and what it does.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

from copilot.stage import catalog, ops
from copilot.stage.graph import Graph

MAX_N = 3  # words in a catalog name

# inflected form -> verb (multi-word forms are matched first); irregular forms listed, regular ones generated
_IRREGULAR = {
    "run": ["ran"], "throw": ["threw", "thrown"], "sit": ["sat", "sitting"], "swim": ["swam", "swimming"],
    "drive": ["drove", "driven", "driving"], "catch": ["caught"], "hold": ["held"], "fall": ["fell", "fallen"],
    "swing": ["swung"], "sink": ["sank", "sunk"], "grow": ["grew", "grown"], "eat": ["ate", "eaten"],
    "drink": ["drank", "drunk"], "fly": ["flew", "flown", "flies"], "carry": ["carries", "carried"],
    "jog": ["jogging", "jogged"], "plan": [], "chop": ["chopping", "chopped"], "nod": ["nodding", "nodded"],
    "plant": [], "dance": ["dancing", "danced"], "slide": ["slid", "sliding"], "shrink": ["shrank", "shrunk"],
    "emit": ["emitting", "emitted"], "rotate": ["rotating", "rotated"], "wave": ["waving", "waved"],
    "move": ["moving", "moved"], "bounce": ["bouncing", "bounced"], "vanish": ["vanishes"],
    "harvest": [], "climb": [], "crouch": ["crouches"], "kneel": ["knelt"], "phone": ["phoning", "phoned"],
}
_SYNONYMS = {  # said verb -> contract verb
    "shove": "push", "nudge": "push", "drag": "pull", "tug": "pull", "toss": "throw", "hurl": "throw",
    "fling": "throw", "lob": "throw", "stroll": "walk", "march": "walk", "sprint": "run", "race": "run",
    "dash": "run", "hop": "jump", "leap": "jump", "lift": "pick_up", "grab": "pick_up", "spin": "rotate",
    "revolve": "orbit", "circle": "orbit", "glide": "slide", "skid": "slide", "sway": "swing", "oscillate": "swing",
    "tumble": "fall", "drop": "fall", "plunge": "sink", "chat": "talk", "speak": "talk", "shout": "call",
    "ride": "drive", "paddle": "swim", "squat": "crouch",
}
_MULTI = {  # multi-word forms (regex over the lower-cased line)
    "pick_up": r"pick(?:s|ed|ing)? (?:\w+ )?up|lift(?:s|ed|ing)? (?:\w+ )?up",
    "put_down": r"put(?:s|ting)? (?:\w+ )?down|set(?:s|ting)? (?:\w+ )?down|plac(?:es|ed|ing) (?:\w+ )?down",
    "slide_down": r"slid(?:es|ing)? down|slid down|roll(?:s|ed|ing)? down",
    "look_at": r"look(?:s|ed|ing)? at",
    "fold_arms": r"fold(?:s|ed|ing)? (?:his|her|their) arms",
    "shake_head": r"shak(?:es|ing)|shook (?:his|her|their) head",
}
_SKIP_SINGLE = {"look", "fold", "shake", "put", "set", "pick", "call", "point", "hold", "plant", "water", "phone",
                "talk", "wave", "stand", "move", "emit", "grow", "float"}  # common words: only as a verb in place


def _forms(v: str) -> list[str]:
    out = [v, v + "s", v + "ed", v + "ing"]
    if v.endswith("e"):
        out += [v + "d", v[:-1] + "ing"]
    if v.endswith(("sh", "ch", "s", "x", "o")):
        out.append(v + "es")
    if v.endswith("y"):
        out += [v[:-1] + "ies", v[:-1] + "ied"]
    return out + _IRREGULAR.get(v, [])


@lru_cache(maxsize=1)
def verbs() -> dict[str, str]:
    out: dict[str, str] = {}
    for v in ops.AGENT_VERBS + ops.OBJECT_VERBS:
        if "_" in v:
            continue
        for f in _forms(v):
            out.setdefault(f, v)
    for said, v in _SYNONYMS.items():
        for f in _forms(said):
            out.setdefault(f, v)
    out.pop("stands", None)  # "stands on the box" is a placement, kept by the spatial words
    return out


_SPATIAL = [  # (phrase, relation), longest first
    ("on top of", "on"), ("in front of", "in_front_of"), ("to the left of", "left_of"), ("to the right of", "right_of"),
    ("left of", "left_of"), ("right of", "right_of"), ("next to", "near"), ("close to", "near"), ("inside", "in"),
    ("into", "in"), ("onto", "on"), ("upon", "on"), ("on", "on"), ("in", "in"), ("under", "under"),
    ("below", "under"), ("beneath", "under"), ("underneath", "under"), ("above", "above"), ("over", "above"),
    ("behind", "behind"), ("beside", "near"), ("near", "near"), ("by", "near"), ("across", "on"), ("along", "on"),
    ("at", "at"),
]
_SPATIAL_RX = re.compile(r"\b(?:" + "|".join(re.escape(p) for p, _ in _SPATIAL) + r")\b")
_SPATIAL_OF = dict(_SPATIAL)
_ATTRS = ("heavy", "light", "rough", "smooth", "red", "blue", "green", "yellow", "black", "white", "big", "small",
          "tiny", "large", "huge", "little", "old", "young", "tall", "short", "wooden", "metal", "empty", "full",
          "elderly")
_MANNER = {"hard": "hard", "harder": "hard", "slowly": "slow", "slow": "slow", "slower": "slow", "fast": "fast",
           "faster": "fast", "quickly": "fast", "gently": "gently", "softly": "gently", "lightly": "gently"}
_DETS = {"a", "an", "the", "his", "her", "their", "its", "my", "your", "our", "some", "this", "that", "another",
         "two", "three", "one"}
_NOT_NOUNS = {"same", "other", "way", "time", "moment", "bit", "lot", "kind", "sort", "thing", "things", "idea",
              "example", "case", "second", "minute", "number", "speed", "force", "angle", "value", "height", "mass",
              "weight", "distance", "end", "top", "side", "front", "back", "left", "right", "middle", "centre",
              "center", "picture", "scene", "lot", "few", "little", "first", "next", "last", "new", "very"}
_HE = {"he", "him", "his", "himself"}
_SHE = {"she", "her", "hers", "herself"}
_THEY = {"they", "them", "their"}
_IT = {"it", "its"}
_ANOTHER = {"another", "second", "other"}
_ON_PLACE = {"moon", "mars", "space", "jupiter"}
_STOP = re.compile(r"\bstop(?:s|ped|ping)?\b(?:\s+(\w+ing))?")
_WORD = re.compile(r"[a-z]+(?:[-'][a-z]+)?")


@dataclass
class Mention:
    at: int            # word index in the line
    end: int           # word index after it
    id: str
    kind: str
    new: bool


@dataclass
class Draft:
    ops: list[dict[str, Any]] = field(default_factory=list)
    prefetch: list[str] = field(default_factory=list)  # nouns the catalog does not know (the ladder starts on them)
    nouns: list[str] = field(default_factory=list)     # the scene nouns said in the line (Whisper's prompt)
    # scene continuity (E3b): which entities of the graph the line names
    old: list[str] = field(default_factory=list)       # by its noun ("a box" again)
    definite: list[str] = field(default_factory=list)  # by "the / his / her ... <noun>"
    pron: list[str] = field(default_factory=list)      # by a pronoun with no antecedent in the line ("past him")
    new: list[str] = field(default_factory=list)       # nouns new to the scene (not "you")


_SUBJECT_NEXT = {"are", "were", "is", "was", "will", "can", "have", "had", "do", "did", "would", "could", "should",
                 "must", "might", "may", "also", "now", "then", "slowly", "start", "begin"}
_SUBJECT_PREV = {"imagine", "if", "when", "as", "and", "suppose", "say", "that", "now", "so", "then", "where", "while"}
_DEFINITE = {"the", "his", "her", "their", "its", "this", "that", "same", "your", "my", "our"}


def _you_subject(words: list[str], i: int) -> bool:
    """"you" is a person on the stage only as the subject ("imagine you are pushing", "you throw"); never in "thank
    you", "see you", "show you how"."""
    nxt = words[i + 1] if i + 1 < len(words) else ""
    prev = words[i - 1] if i else ""
    if prev in ("thank", "see", "to", "for", "with", "show", "tell", "told", "ask", "give", "let", "help", "of"):
        return False
    return nxt in _SUBJECT_NEXT or nxt in verbs() or prev in _SUBJECT_PREV


def _plurals(w: str) -> list[str]:
    out = [w, w + "s"]
    if w.endswith(("s", "x", "ch", "sh")):
        out.append(w + "es")
    if w.endswith("y") and w[-2:-1] not in "aeiou":
        out.append(w[:-1] + "ies")
    return out


@lru_cache(maxsize=1)
def index() -> dict[str, str]:
    """Every name the stage draws (plural forms too) -> its singular name; the kind is decided per mention."""
    c = catalog.catalog()
    names: list[str] = [w for w in catalog.PEOPLE if w not in _HE | _SHE | _THEY] + list(catalog.GROUND)         + list(catalog.FLUIDS)
    for key in ("props", "species", "backdrops"):
        for r in c[key]:
            names += [r["id"].replace("_", " ")] + list(r["names"])
    out: dict[str, str] = {}
    for n in names:
        for f in _plurals(n.lower()):
            out.setdefault(f, n.lower())
    out.update({"men": "man", "women": "woman", "children": "child", "people": "people"})
    return out


def _kind_of(phrase: str, prev: str) -> Optional[str]:
    """The entity kind a said phrase draws as, or None (not a stage noun)."""
    w = index().get(phrase)
    if w is None:
        return None
    if w in catalog.PEOPLE:
        return "agent"
    if catalog.species(w):
        return "animal"
    if w in _ON_PLACE and prev in ("on", "in", "to"):
        return "place"
    if w in catalog.GROUND + catalog.FLUIDS:
        return "surface"
    if catalog.prop(w):
        return "prop"
    return "place" if catalog.backdrop(w) else None


def _slug(w: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", w.lower()).strip("_")[:16]
    return s if s and s[0].isalpha() else "e_" + s


def _new_id(base: str, taken: set[str]) -> str:
    i, cand = 1, base
    while cand in taken:
        i += 1
        cand = f"{base}{i}"
    taken.add(cand)
    return cand


def _same(e: Any, phrase: str) -> bool:
    a, b = e.w.lower(), phrase.lower()
    return a == b or a.rstrip("s") == b.rstrip("s") or a.split()[-1] == b.split()[-1]


def draft(text: str, g: Optional[Graph] = None) -> Draft:
    """Draft ops for one line against the scene so far (a fold of the log)."""
    g = g or Graph()
    out = Draft()
    low = re.sub(r"\byou['’]re\b", "you are", text.lower())
    words = [m.group(0) for m in _WORD.finditer(low)]
    starts = [m.start() for m in _WORD.finditer(low)]
    taken = set(g.ents) | set(g.actions) | set(g.laws) | set(g.diagrams)
    mentions: list[Mention] = []
    adds: dict[str, dict[str, Any]] = {}
    kinds = {e.id: e.kind for e in g.ents.values()}
    sex = {e.id: (catalog.cast().get(e.draw[5:], {}).get("sex", "") if e.draw.startswith("cast:") else "")
           for e in g.ents.values()}

    unknown_before = False
    i = 0
    while i < len(words):
        hit = None
        for n in range(min(MAX_N, len(words) - i), 0, -1):
            phrase = " ".join(words[i:i + n])
            k = _kind_of(phrase, words[i - 1] if i else "")
            if k and not (phrase == "you" and not _you_subject(words, i)):
                hit = (phrase, n, k)
                break
        if hit is None:
            w = words[i]
            # "a kettle ... steam comes out of it": "it" is the kettle (said, not in the kit), not a thing on stage
            dummy = w in _IT and words[i + 1:i + 2] and words[i + 1] in ("is", "was", "gets", "got", "starts")
            ref = None if w in _IT and (unknown_before or dummy) else _pronoun(w, mentions, g, kinds, sex)
            if ref:
                mentions.append(Mention(i, i + 1, ref, kinds.get(ref, ""), False))
                if ref in g.ents and ref not in adds:
                    out.pron.append(ref)
            elif w in _DETS and i + 1 < len(words):
                noun = _unknown_noun(words, i + 1)
                if noun:
                    same = next((e.id for e in g.ents.values() if _same(e, noun)), None)
                    if same:  # "a rocket" again: the rocket on stage (a stand-in picture)
                        out.old.append(same)
                        if w in _DEFINITE:
                            out.definite.append(same)
                    else:
                        out.prefetch.append(noun)
                        unknown_before = True
            i += 1
            continue
        phrase, n, k = hit
        phrase = index()[phrase]
        prev = words[i - 1] if i else ""
        again = prev in _ANOTHER or (i > 1 and words[i - 2] in _ANOTHER)
        eid = None
        if not again:
            eid = next((m.id for m in reversed(mentions) if m.id in adds and _same_add(adds[m.id], phrase)), None)
            if eid is None:
                eid = next((e.id for e in sorted(g.ents.values(), key=lambda e: -e.said)
                            if e.kind == k and _same(e, phrase)), None)
        new = eid is None
        if new:
            eid = _new_id(_slug(phrase), taken)
            attr = [w for w in words[max(0, i - 3):i] if w in _ATTRS]
            add = {"op": "add", "id": eid, "kind": k, "w": phrase}
            if attr:
                add["attr"] = attr
            adds[eid] = add
            kinds[eid] = k
            p = catalog.person(phrase)
            sex[eid] = (p[0] or "") if p else ""
            if phrase != "you":
                out.new.append(phrase)
        elif eid in g.ents:
            out.old.append(eid)
            b = i - 1
            while b > 0 and (words[b] in _ATTRS or words[b] in _INTENS):
                b -= 1
            if (words[b] if b >= 0 else "") in _DEFINITE:
                out.definite.append(eid)
        mentions.append(Mention(i, i + n, eid, k, new))
        out.nouns.append(phrase)
        i += n

    out.ops.extend(adds.values())
    acts = _acts(low, words, starts, mentions, g, kinds, taken)
    out.ops.extend(_relations(low, words, starts, mentions, kinds, acts))
    out.ops.extend(acts)
    out.ops.extend(_ends(low, words, starts, mentions, g))
    out.ops = out.ops[:ops.MAX_OPS]
    out.prefetch = list(dict.fromkeys(out.prefetch))
    out.new = list(dict.fromkeys(out.new + out.prefetch))  # "a kettle": not in the kit, new to the scene all the same
    return out


_NOT_HEAD = {"and", "or", "of", "with", "in", "on", "at", "to", "from", "that", "which", "who", "is", "was", "are",
             "were", "for", "into", "onto", "by", "as", "than", "then"}


def _nounish(w: str) -> bool:
    return w not in _NOT_NOUNS and w not in verbs() and len(w) > 2 and w not in _DETS and w not in _NOT_HEAD \
        and not w.endswith(("ed", "ing", "ly"))


_INTENS = ("very", "really", "so", "quite", "too", "extremely")


def _unknown_noun(words: list[str], j: int) -> str:
    """The head noun of a determiner phrase the kit does not know ("a DC circuit" -> circuit, "a kettle sits" ->
    kettle); "" when the phrase is a catalog name ("an inclined plane") or no noun."""
    while j < len(words) and (words[j] in _ATTRS or words[j] in _INTENS):
        j += 1
    if j >= len(words) or any(_kind_of(" ".join(words[j:j + n]), "") for n in range(1, MAX_N + 1)):
        return ""
    head = words[j]
    if j + 1 < len(words) and _nounish(words[j + 1]) and not _kind_of(words[j + 1], ""):
        head = words[j + 1]  # a compound: the last noun is the thing
    elif len(head) <= 2 or head in _NOT_NOUNS or head in verbs() or head in _DETS:
        return ""
    return head


def _same_add(add: dict[str, Any], phrase: str) -> bool:
    a, b = add["w"], phrase
    return a == b or a.rstrip("s") == b.rstrip("s")


def _pronoun(w: str, mentions: list[Mention], g: Graph, kinds: dict[str, str], sex: dict[str, str]) -> Optional[str]:
    if w in _HE | _SHE | _THEY:
        want = "m" if w in _HE else "f" if w in _SHE else ""
        for m in reversed(mentions):
            if kinds.get(m.id) == "agent" and (not want or sex.get(m.id) in (want, "")):
                return m.id
        for e in sorted(g.ents.values(), key=lambda e: -e.said):
            if e.kind == "agent" and (not want or sex.get(e.id) in (want, "")):
                return e.id
        return None
    if w in _IT:
        for m in reversed(mentions):
            if kinds.get(m.id) in ("prop", "animal"):
                return m.id
        e = next((e for e in sorted(g.ents.values(), key=lambda e: -e.said) if e.kind in ("prop", "animal")), None)
        return e.id if e else None
    return None


def _word_at(starts: list[int], pos: int) -> int:
    """The index of the word starting at or after character `pos`."""
    return next((i for i, s in enumerate(starts) if s >= pos), len(starts))


def _verb_hits(low: str, words: list[str], starts: list[int]) -> list[tuple[int, int, str]]:
    """(word index, words used, verb) for each verb said, in order."""
    hits: list[tuple[int, int, str]] = []
    used: set[int] = set()
    for v, rx in _MULTI.items():
        for m in re.finditer(rf"\b(?:{rx})\b", low):
            a, b = _word_at(starts, m.start()), _word_at(starts, m.end())
            hits.append((a, max(1, b - a), v))
            used.update(range(a, b))
    lex = verbs()
    for i, w in enumerate(words):
        if i in used or w not in lex:
            continue
        v = lex[w]
        if w in _SKIP_SINGLE or (v in _SKIP_SINGLE and w == v):
            prev = words[i - 1] if i else ""
            if prev in _DETS or prev in ("to",) and v in ("water", "plant"):  # "the water", "a phone"
                continue
        hits.append((i, 1, v))
    return sorted(hits)


def _acts(low: str, words: list[str], starts: list[int], mentions: list[Mention], g: Graph,
          kinds: dict[str, str], taken: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    noun_at = {i for m in mentions for i in range(m.at, m.end)}
    stopped = {_word_at(starts, m.start()) + 1 for m in _STOP.finditer(low)}
    for at, n, v in _verb_hits(low, words, starts):
        if at in noun_at or at in stopped:
            continue  # "a swing" is a prop, "the fall" a noun: a mention wins; "stops pushing" ends the push
        before = [m for m in mentions if m.end <= at]
        after = [m for m in mentions if m.at > at]  # "puts it down": the object can sit inside the verb
        agent_verb = v in ops.AGENT_VERBS
        object_verb = v in ops.OBJECT_VERBS
        who = next((m for m in reversed(before) if kinds.get(m.id) in ("agent", "animal")), None)
        if agent_verb and who is not None and (kinds[who.id] == "agent" or v in ops.ANIMAL_VERBS):
            act: dict[str, Any] = {"op": "act", "id": _act_id(v, taken), "verb": v, "agent": who.id}
            chase = v in ("run", "walk", "jog") and words[at + n:at + n + 1] == ["after"]  # "a dog running after a cat"
            if v in ops.NEEDS_OBJ or v in ("throw", "carry", "push", "pull", "drive", "roll") or chase:
                obj = next((m for m in after if kinds.get(m.id) in ("prop", "animal", "agent") and m.id != who.id),
                           None)
                if obj is None:  # "now he pushes harder", "she puts it down": what the agent works on now
                    cur = next((a.obj for a in g.active(who.id) if a.obj), None) or next(
                        (r.b for r in g.rels if r.kind == "holding" and r.a == who.id), None)
                    obj = Mention(0, 0, cur, "", False) if cur else None
                if obj is None:
                    if v in ops.NEEDS_OBJ:
                        continue
                else:
                    act["obj"] = obj.id
        elif object_verb:
            thing = next((m for m in reversed(before) if kinds.get(m.id) in ("prop", "animal", "surface")), None)
            if thing is None:
                continue
            act = {"op": "act", "id": _act_id(v, taken), "verb": v, "agent": thing.id}
        else:
            continue
        d = _direction(words[at + n:at + n + 6], mentions, at + n)
        if d:
            act["dir"] = d
        elif v in ("walk", "jog", "run", "push", "carry", "drive", "swim", "move") and v != "pull":
            act["dir"] = "right"
        elif v == "fall":
            act["dir"] = "down"
        manner = next((_MANNER[w] for w in words[max(0, at - 1):at + n + 4] if w in _MANNER), None)
        if manner:
            act["manner"] = manner
        if v == "hold" and "obj" in act:
            out.append({"op": "relate", "a": act["agent"], "kind": "holding", "b": act["obj"]})
        if v in ("carry", "throw", "pick_up") and "obj" in act and g.holder(act["obj"]) != act["agent"]:
            out.append({"op": "relate", "a": act["agent"], "kind": "holding", "b": act["obj"]})
        out.append(act)
    return out


def _act_id(v: str, taken: set[str]) -> str:
    base, n = v.split("_")[0][:6], 1
    while f"{base}{n}" in taken:
        n += 1
    taken.add(f"{base}{n}")
    return f"{base}{n}"


def _direction(tail: list[str], mentions: list[Mention], base: int) -> Optional[str]:
    s = " ".join(tail)
    if re.match(r"^(?:\w+ ){0,2}(?:to the |towards the |toward the )?(left|right)\b", s):
        return re.match(r"^(?:\w+ ){0,2}(?:to the |towards the |toward the )?(left|right)\b", s).group(1)
    m = re.match(r"^(?:\w+ ){0,2}(up|upwards|down|downwards)\b", s)
    if m:
        return "up" if m.group(1).startswith("up") else "down"
    m = re.match(r"^(?:\w+ ){0,2}(towards?|away from)\b", s)
    if m:
        k = len(m.group(0).split())
        ref = next((x for x in mentions if x.at >= base + k - 1), None)
        if ref is not None:
            return ("toward:" if m.group(1).startswith("toward") else "away:") + ref.id
    return None


def _relations(low: str, words: list[str], starts: list[int], mentions: list[Mention], kinds: dict[str, str],
               acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sat = {a["agent"] for a in acts if a.get("verb") == "sit"}
    seen: set[tuple[str, str]] = set()
    for m in _SPATIAL_RX.finditer(low):
        at = _word_at(starts, m.start())
        k = len(m.group(0).split())
        rel = _SPATIAL_OF[m.group(0)]
        b = next((x for x in mentions if x.at >= at + k and x.at <= at + k + 3), None)
        a = next((x for x in reversed(mentions) if x.end <= at and x.end >= at - 6), None)
        if a is None or b is None or a.id == b.id or kinds.get(b.id) == "place" or kinds.get(a.id) == "place":
            continue
        if kinds.get(a.id) == "surface":
            continue  # "the floor in the room": the ground is drawn by the backdrop
        if rel == "on" and a.id in sat:
            rel = "sitting_on"
        if rel == "on" and kinds.get(b.id) == "agent":
            continue  # "rain falls on a man": not a placement
        if (a.id, rel) in seen:
            continue
        seen.add((a.id, rel))
        out.append({"op": "relate", "a": a.id, "kind": rel, "b": b.id})
    return out


def _ends(low: str, words: list[str], starts: list[int], mentions: list[Mention], g: Graph) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _STOP.finditer(low):
        at = _word_at(starts, m.start())
        who = next((x for x in reversed(mentions) if x.end <= at), None)
        verb = verbs().get(m.group(1) or "", "")
        for a in g.active(who.id if who else None):
            if who is None and len(g.active()) > 1:
                break
            if not verb or a.verb == verb:
                out.append({"op": "end", "id": a.id})
    return out
