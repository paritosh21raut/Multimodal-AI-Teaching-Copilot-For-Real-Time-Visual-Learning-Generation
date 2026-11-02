"""Story lines -> beats and speech (V3 ST1), deterministic, 0 tokens. Everything returned is said words.

    speech(text)   "Ravi said, "I love football."" / "Asha replied, me too!" / ""Me too," said Asha" /
                   "Ravi asked Asha, do you play?" -> Speech(who, verb kind, to, words); "Ravi said," alone ->
                   Speech with no words (the next line is the quote: Whisper splits them)
    beat(text)     when ("1905", "years later"), where ("Bern", "the clouds"), people (names, "a young clerk"),
                   a sequence marker ("then", "one day"), the caption and the picture query
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from copilot.scene import pictures as pics

CAPTION_MAX = 110
BUBBLE_MAX = 140

# ---- speech ---------------------------------------------------------------------------------------------------
_VERB_KIND = {"said": "say", "says": "say", "say": "say", "told": "say", "tells": "say", "added": "say",
              "adds": "say", "explained": "say", "explains": "say", "laughed": "say", "smiled": "say",
              "asked": "ask", "asks": "ask", "wondered": "ask",
              "replied": "reply", "replies": "reply", "answered": "reply", "answers": "reply", "responded": "reply",
              "shouted": "shout", "shouts": "shout", "yelled": "shout", "yells": "shout", "exclaimed": "shout",
              "cried": "shout", "screamed": "shout", "called": "shout",
              "whispered": "whisper", "whispers": "whisper", "murmured": "whisper",
              # test55: "The girl was shouting. It is in the garden." (Whisper put a full stop for the comma)
              "saying": "say", "telling": "say", "asking": "ask", "replying": "reply", "answering": "reply",
              "shouting": "shout", "yelling": "shout", "whispering": "whisper"}
_PROGRESSIVE = frozenset(v for v in _VERB_KIND if v.endswith("ing"))
_VERBS = "|".join(sorted(_VERB_KIND, key=len, reverse=True))
_ADDRESS = {"asked", "asks", "told", "tells", "answered", "answers", "wondered", "called", "asking", "telling"}  # "asked Asha, ..."
_AUX = r"(?!(?:is|was|are|were|be|been|being|has|had|have|will|would|can|could|should|may|might|must)\b)"
_SPEAKER = (r"(?:(?i:the|his|her|their|my|our|a|an)\s+(?:" + _AUX + r"[a-z]+\s+)?" + _AUX + r"[a-z]+(?=\s+(?:then\s+|also\s+)?(?:(?:was|is|were|kept)\s+)?(?:" + _VERBS
            + r")\b)|[A-Z][a-z]*(?:\s+[A-Z][a-z]+)?|he|she|they)")
_TARGET = r"(?:[A-Z][a-z]+|him|her|them|me|us|(?:the|his|her|their)\s+[a-z]+)"
_LEAD = r"^\W*(?:(?i:and|then|so|now|but|one day|later|suddenly|finally|next|after that|once upon a time|long ago)\W+)*"  # ST4: the cue line's speech
_QUOTES = "\"“”‘’'"
_SAY_FIRST = re.compile(
    _LEAD + rf"(?P<who>{_SPEAKER})\s+(?:then\s+|also\s+|quickly\s+|softly\s+|loudly\s+)?(?:(?:was|is|were|kept)\s+)?(?P<verb>{_VERBS})\b"
    r"(?:\s+(?i:himself|herself|themselves|itself)(?=\s*[,:]))?"  # ST4: "asked himself, why ...": no addressee
    rf"(?:\s+(?:to\s+(?P<to>{_TARGET})|(?P<obj>{_TARGET})(?=\s*[,:\"“]|\s+(?:do|did|are|is|can|will|what|why|how|where|when|who|if)\b)))?"
    r"\s*(?P<rest>.*)$", re.DOTALL)
_SAY_AFTER = re.compile(
    r"^\W*[\"“'](?P<q>[^\"”]{1,200}?)[,.!?]?[\"”']\s*,?\s*(?:(?P<verb>" + _VERBS + r")\s+(?P<who>"
    + _SPEAKER + r")|(?P<who2>" + _SPEAKER + r")\s+(?P<verb2>" + _VERBS + r"))\b.*$")
_NOT_WORDS = re.compile(r"^(?:that|nothing|no\b|yes to|so\b|it\b|this\b|something|a lot|many|the same|goodbye to|"
                        r"hello to|about|of|in|on|with)\b", re.IGNORECASE)
_ARTICLE_ONLY = {"a", "an", "the", "his", "her", "their", "my", "our"}


@dataclass
class Speech:
    who: str          # as said: "Ravi", "the boy", "he"
    kind: str         # say | ask | shout | whisper | reply
    to: str = ""
    words: str = ""   # "" = the words come on the next line


def _clean_words(s: str) -> str:
    s = s.strip().strip(_QUOTES + " ,:;").strip()
    s = re.sub(r"\s+", " ", s)
    s = s[:1].upper() + s[1:]
    if len(s) > BUBBLE_MAX:
        s = s[:BUBBLE_MAX].rsplit(" ", 1)[0] + "…"
    return s


def speech(text: str) -> Optional[Speech]:
    """The line's speech, or None (narration). Indirect speech ("said that he was tired") and "told him a story" are
    narration."""
    t = text.strip()
    m = _SAY_AFTER.match(t)
    if m:
        who = m.group("who") or m.group("who2")
        verb = (m.group("verb") or m.group("verb2")).lower()
        return Speech(who=who, kind=_VERB_KIND[verb], words=_clean_words(m.group("q")))
    m = _SAY_FIRST.match(t)
    if not m:
        return None
    who, verb = m.group("who"), m.group("verb").lower()
    if who.split()[-1].lower() in _ARTICLE_ONLY and not (len(who) == 1 and who.isupper()):
        return None  # "A said, ...": a character called A (one capital letter) is a name
    to = m.group("to") or (m.group("obj") if verb in _ADDRESS else "") or ""
    if m.group("obj") and verb not in _ADDRESS:
        return None  # "said Football is fun": not an addressee; read as narration rather than guess
    rest = m.group("rest") or ""
    quoted = any(q in rest for q in "\"“”")
    rest_c = _clean_words(rest)
    if not rest_c:
        return Speech(who=who, kind=_VERB_KIND[verb], to=to) if re.search(r"[,:]\s*$|^\W*$", rest) else None
    comma = bool(re.match(r"^\W*[,:]", rest) or verb in _PROGRESSIVE and re.match(r"^\s*[.;]", rest))
    if verb in _PROGRESSIVE and not comma and not quoted:
        return None  # "Perry was saying this metal glows": the words' start is not marked (the LLM reads it)
    rest_c = _clean_words(rest.lstrip(" .;")) if verb in _PROGRESSIVE else rest_c
    if not quoted and not comma and verb not in _ADDRESS:
        return None  # "the teacher said we should start": indirect speech is narration
    if not quoted and (not comma and _NOT_WORDS.match(rest_c) or verb in ("told", "tells", "explained", "explains")
                       and not to):
        return None
    if not quoted and not re.match(r"^\W*[,:]", rest) and verb in ("laughed", "smiled", "called", "added", "adds"):
        return None  # "laughed at the joke", "called the doctor": narration
    return Speech(who=who, kind=_VERB_KIND[verb], to=to, words=rest_c)


def quote_only(text: str) -> str:
    """The next line after "Ravi said,": the whole line is the words."""
    return _clean_words(text)


_ASIDE = re.compile(
    r"^\W*(?:(?:okay|ok|so|now|right|alright|sorry)\W+)*(?:(?:everyone|class|students|children)\s*[,!?]"
    r"|let me (?:move|go|turn|switch|change|scroll)\b"
    r"|(?:look|see)\s+(?:at\s+)?(?:the|this)\s+(?:picture|slide|screen|board|image)"
    r"|look (?:here|carefully)|listen (?:carefully|to me)|write (?:this|it) down|can (?:you|everyone|anyone|everybody|anybody) (?:all )?see|is everyone (?:with me|following))",
    re.IGNORECASE)


def aside(text: str) -> bool:
    """ST4: the teacher talking to the class ("Okay, look at the picture carefully"): not a story line."""
    if re.search(rf"\b(?:{_VERBS})\b", text, re.IGNORECASE) or any(q in text for q in "\"“”"):
        return False  # review: "Look here, said the king, ..." is story speech (the LLM may read it)
    return bool(_ASIDE.match(text))


# ---- beats ----------------------------------------------------------------------------------------------------
_YEAR = re.compile(r"\b(?:in|by|around|during|until|from|back in|of)\s+(?:the\s+year\s+)?((?:1[0-9]|20)\d{2})\b"
                   r"(?!\s*(?:kg|g|m|km|metres?|meters?|people|times|%|degrees))", re.IGNORECASE)
_TIME = re.compile(
    r"\b(?:(?:many|a few|some|two|three|four|five|six|seven|eight|nine|ten|twenty|\d+)\s+(?:years?|days?|weeks?|months?|hours?|minutes?|seconds?)\s+later"
    r"|(?:years?|days?|weeks?|months?) later|the next (?:day|morning|night|week|month|year|summer|winter)"
    r"|one (?:day|morning|evening|night|summer|winter|afternoon)|that (?:night|evening|morning|day|afternoon)"
    r"|long ago|later that (?:day|night|year)|soon after(?:wards)?|after (?:a while|some time|many years)"
    r"|that (?:winter|summer|spring|autumn|year)|(?:a|one) (?:decade|century) later|decades later|centuries later)\b",
    re.IGNORECASE)
_SEQ = re.compile(r"^\W*(?:(?:and|so|now|okay|ok)\W+)*(?:then|next|later|after that|afterwards|soon|finally|"
                  r"eventually|meanwhile|suddenly|at last|in the end)\b", re.IGNORECASE)
_PREP = r"(?:in|at|to|into|from|near|inside|through|across|reaches|reached|reach|enters|entered|onto|towards|toward)"
_PREP_COMMON = _PREP[:-1] + r"|on)"  # ST4: "on a mountain" (a place word only; "depended on Mary" is no place)
_PLACE_PROPER = re.compile(rf"\b{_PREP}\s+(?:the\s+)?((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+){{0,2}})\b")
STORY_PLACES = frozenset({
    "office", "patent office", "school", "home", "house", "garden", "park", "forest", "village", "lab", "laboratory",
    "kitchen", "field", "farm", "beach", "desert", "lungs", "lung", "heart", "vein", "veins", "artery", "arteries",
    "capillaries", "body", "stomach", "intestine", "blood", "bloodstream", "leaf", "leaves", "roots", "soil", "ground",
    "library", "classroom", "market", "palace", "castle", "ship", "train", "university", "playground", "room",
    "city", "town", "jungle", "cave", "island", "sun", "moon", "earth", "planet", "plant", "tree", "brain", "cell",
    "kidney", "kidneys", "liver", "mountain", "mountains", "hill", "hills", "river", "sea", "ocean", "lake"})
_PLACE_WORDS = frozenset(w for ws in pics.PLACES.values() for w in ws) | STORY_PLACES
_MOVE_PLACE = re.compile(  # ST4: "wandered into a muddy ditch", "climbed onto the haystack": a place said by the move
    r"\b(?:went|goes|walked|walks|ran|runs|moved|moves|climbed|climbs|wandered|wanders|flew|flies|drove|drives|"
    r"sailed|sails|travelled|traveled|travels|came|comes|returned|returns|jumped|jumps|rode|rides|swam|swims|"
    r"hurried|rushed|crawled|crept|fled|escaped)\s+(?:up\s+|down\s+|back\s+|out\s+|away\s+)?"
    r"(?:into|onto|to|towards|toward|inside|across|through)\s+((?:the|a|an)\s+(?:[a-z]+\s+)?[a-z]+)\b")
_NOT_PLACE_HEAD = frozenset("way time end top bottom middle side front back rest idea moment of and or with for "
                            "his her their its decision problem problems rage hurry stop halt sleep agreement race pace "
                            "conclusion standstill fight trouble deal close realisation realization life power "
                            "rescue aid help start finish surprise shock".split())
_PLACE_COMMON = re.compile(rf"\b{_PREP_COMMON}\s+((?:the|a|an|its|his|her|their|our)\s+(?:[a-z]+\s+)?[a-z]+)\b")
PERSON_NOUNS = frozenset({
    "man", "woman", "boy", "girl", "child", "kid", "clerk", "scientist", "king", "queen", "prince", "princess",
    "farmer", "teacher", "student", "doctor", "soldier", "merchant", "sailor", "friend", "mother", "father",
    "brother", "sister", "son", "daughter", "grandmother", "grandfather", "worker", "traveller", "traveler",
    "inventor", "physicist", "chemist", "explorer", "monk", "officer", "judge", "pilot", "cook", "baker", "lady",
    "gentleman", "professor", "engineer", "mathematician", "astronomer", "biologist", "nurse", "artist", "writer",
    "poet", "shepherd", "fisherman", "hunter", "knight", "emperor", "villager", "neighbour", "neighbor", "baby"})
_ADJ = r"(?:(?:young|old|little|poor|rich|brave|kind|wise|tired|clever|curious|small|tiny|famous|great|"\
       r"hungry|lonely|happy|sad|certain|german|indian|english|french|greek|italian)\s+){0,2}"
_PERSON = re.compile(rf"\b(?:a|an|the|one|his|her|their|my)\s+({_ADJ}(?:{'|'.join(sorted(PERSON_NOUNS, key=len, reverse=True))}))\b",
                     re.IGNORECASE)
_NOT_NAME = frozenset("""a an the in on at to of and but or so then now next later after before when while if this that
these those there here it its he she they we you i me him her them us his their our my your one okay ok yes no well
let imagine once suppose picture think consider look follow today yesterday tomorrow years year long many some every
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
september october november december first finally meanwhile suddenly soon eventually also what why how who where
mr mrs ms dr sir lord god oh hey hello hi""".split())


_THING_TAIL = frozenset("""prize award medal law laws theory war revolution company institute institution society
academy museum university college school river mountain mountains ocean sea lake kingdom empire day bridge church
temple tower palace street road station hospital library prize prizes cup games treaty act party""".split())


@dataclass
class Beat:
    when: str = ""
    where: str = ""
    names: list[str] = field(default_factory=list)    # capitalised names: "Albert Einstein", "Ravi"
    people: list[str] = field(default_factory=list)   # person nouns: "a young clerk"
    marker: str = ""                                  # "then", "one day", "years later"
    caption: str = ""
    query: str = ""

    @property
    def cuts(self) -> bool:
        return bool(self.marker or self.when or self.where)


_FILLER = re.compile(r"^\W*(?:(?:okay|ok|so|now|alright|all right|right|well|and|yeah|yes|yep|hmm|um|uh)\W+)+",
                     re.IGNORECASE)  # test56: "Yeah." alone made a scene
_PREAMBLE = re.compile(r"^\W*(?:let me tell you|here(?:'s| is)|i(?:'ll| will) tell you|this is|let me narrate)\s+"
                       r"(?:a|the|one|this)?\s*(?:little\s+|short\s+|true\s+|famous\s+)?(?:story|tale)\b"
                       r"(?:\s+(?:of|about)\b)?\W*", re.IGNORECASE)


def caption(text: str) -> str:
    """The said words, shortened: the story preamble and fillers off, at most CAPTION_MAX at a word boundary."""
    s = _FILLER.sub("", text.strip())
    s = _FILLER.sub("", _PREAMBLE.sub("", s)).strip()
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    if len(s) > CAPTION_MAX:
        s = s[:CAPTION_MAX].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


def _names(text: str, places: set[str]) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text):
        ws = [w for w in m.group(0).split() if w.lower() not in _NOT_NAME]
        if not ws:
            continue
        n = " ".join(ws)
        if n in places or any(n in p.split() for p in places) or len(n) < 2:
            continue
        if len(ws) == 1 and n.endswith("ing") and not text[:m.start()].strip(" \"'“"):
            continue  # test55: "Seeing these metal glues ..." : a verb that starts the line is no name
        if ws[-1].lower() in _THING_TAIL:  # ST2: "the Nobel Prize", "the Royal Society" are no people
            continue
        if n not in out:
            out.append(n)
    return out


def beat(text: str) -> Beat:
    b = Beat()
    y = _YEAR.search(text)
    t = _TIME.search(text)
    b.when = y.group(1) if y else (t.group(0).lower() if t else "")
    s = _SEQ.search(text)
    b.marker = (t.group(0).lower() if t else "") or (s.group(0).strip(" ,.").split()[-1].lower() if s else "")
    plain = re.sub(r"(\w)['’]s\b", r"\1", text)  # test51: "at the patent's office" is the patent office
    proper = [m.group(1) for m in _PLACE_PROPER.finditer(plain)
              if m.group(1).split()[0].lower() not in _NOT_NAME]
    common = []
    for m in _PLACE_COMMON.finditer(plain):
        ph = m.group(1).lower()
        ws = ph.split()
        tail = " ".join(ws[-2:]) if len(ws) >= 3 else ws[-1]
        if tail in _PLACE_WORDS or ws[-1] in _PLACE_WORDS:
            common.append(ph if ws[0] in ("the", "a", "an") else "the " + " ".join(ws[1:]))
    if not common:
        m = _MOVE_PLACE.search(plain)
        if m and m.group(1).split()[-1] not in PERSON_NOUNS and not _NOT_PLACE_HEAD & set(m.group(1).split()):
            common = [m.group(1).lower()]
    b.where = (proper or common or [""])[0]
    b.names = _names(text, set(proper))
    b.people = [re.sub(r"\s+", " ", m.group(0).strip()).lower() for m in _PERSON.finditer(text)]
    b.caption = caption(text)
    return b


def head_noun(phrase: str) -> str:
    ws = re.findall(r"[a-z]+", phrase.lower())
    ws = [w for w in ws if w not in _ARTICLE_ONLY and w not in ("one", "young", "old", "little")]
    if "of" in ws and ws.index("of") > 0:  # "drop of water" -> drop, "red blood cell" -> cell
        ws = ws[:ws.index("of")]
    return ws[-1] if ws else ""


def picture_noun(phrase: str) -> str:
    """The emoji noun of a cast member or a beat ("a drop of water" -> droplet, "a young clerk" -> office worker,
    a name -> person)."""
    low = " ".join(re.findall(r"[a-z]+", phrase.lower()))
    for k, v in _PICTURE_ALIAS.items():
        if re.search(rf"\b{k}\b", low):
            return v
    h = head_noun(phrase)
    if not h:
        return "person"
    if phrase[:1].isupper() and h not in PERSON_NOUNS and h not in _PLACE_WORDS:
        return "person"  # a name: no face is guessed from it
    return h


_PICTURE_ALIAS = {"drop of water": "droplet", "water drop": "droplet", "raindrop": "droplet", "droplet": "droplet",
                  "red blood cell": "drop of blood", "blood cell": "drop of blood", "clerk": "office worker",
                  "physicist": "scientist", "chemist": "scientist", "inventor": "scientist",
                  "mathematician": "scientist", "astronomer": "scientist", "biologist": "scientist",
                  "professor": "teacher", "child": "child", "kid": "child", "lady": "woman", "gentleman": "man"}


# ---- continuity (ST2) -----------------------------------------------------------------------------------------
_SHE = frozenset({"woman", "girl", "lady", "queen", "princess", "mother", "sister", "daughter", "grandmother", "wife",
                  "aunt", "niece", "mom", "mum", "empress", "nun", "actress", "waitress", "goddess"})
_HE = frozenset({"man", "boy", "gentleman", "king", "prince", "father", "brother", "son", "grandfather", "husband",
                 "uncle", "nephew", "dad", "emperor", "monk", "knight", "actor", "waiter", "god"})
_PRONOUN_LINE = re.compile(r"\b(he|she|they|him|her|them|his|their)\b", re.IGNORECASE)
_PRONOUN_CASE = {"he": "he", "him": "he", "his": "he", "she": "she", "her": "she", "they": "they", "them": "they",
                 "their": "they"}


def gender_of(phrase: str) -> str:
    """"he" / "she" from a said noun ("a young woman", "his sister", "the mother of Ravi"), "" = not said. Never from a
    name ("Billie Jean King")."""
    h = head_noun(phrase)
    if not h or h not in _SHE | _HE:
        return ""
    ws = re.findall(r"[A-Za-z]+", phrase)
    if any(w.lower() == h and w[:1].isupper() and (k > 0 or len(ws) == 1) for k, w in enumerate(ws)):
        return ""  # a capitalised "King" is part of a name
    return "she" if h in _SHE else "he"


def pronoun(text: str) -> str:
    """The first person pronoun of a narrative line: "he" / "she" / "they" ("" = none). "his" / "her" count."""
    m = _PRONOUN_LINE.search(text)
    return _PRONOUN_CASE[m.group(1).lower()] if m else ""


_SUBJECT = re.compile(r"(?:^|[,.;:]\s*|\b(?:then|and|so|later|soon|when)\s+)(he|she)\b", re.IGNORECASE)


def subject(text: str) -> str:
    """"he" / "she" as the subject of a line that also names someone ("In 1895, she met Pierre"); "his" / "her" /
    "him" are not ("Pierre met her" names its subject)."""
    m = _SUBJECT.search(text)
    return m.group(1).lower() if m else ""
