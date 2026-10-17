"""Is a spoken sentence fit to be a slide line as said? (F-013 S3 item 4, the garbage gate)

The coverage guard, the empty-act filler and the fallback put the teacher's own sentences on the projector. Over tests
1–30 that added lines such as "Recall that thermal energy continuously creates pair of free electrons and holes",
"These devices will be discussed in later chapter", "You to understand all kinds of semiconductor devices",
"Single inverted comma b1 semicolon end end module" and "[unclear location, likely mis-heard]". Deterministic, no
model: a line with a problem is not shown (and is logged by the caller); the model's own items are not judged here.
"""
from __future__ import annotations

import re

# words about the transcript itself, never lecture content
_META = re.compile(r"\[[^\]]*[a-z]{4,}[^\]]*\]|\bmis-?heard\b|\binaudible\b|\bunclear (?:word|location|audio)\b",
                   re.IGNORECASE)
# code read aloud (test26 Verilog): punctuation spoken as words
_CODE = re.compile(r"\b(?:semicolon|inverted comma|(?:round|curly|square) brackets?|brackets? (?:open|close)d?|"
                   r"end ?module|end ?if|begin end|equals equals|double quotes?)\b", re.IGNORECASE)
# pointers to other parts of the course, not facts: "Recall that ...", "will be discussed in later chapter"
_REFERENCE = re.compile(r"^(?:(?:the |our |today'?s )?(?:main |first |second |third |fourth |fifth |sixth |next |last |"
                        r"final |\w+ in )?(?:topic|chapter|lesson|subject|unit) (?:is|for today)|recall that|remember that|as (?:previously|already|we have|we) (?:discussed|mentioned|"
                        r"seen|saw|said)|before (?:discussing|we discuss)|in today'?s world|that'?s it|there you (?:go|"
                        r"went))\b|\b(?:will be (?:discussed|covered|explained)|(?:in|of) (?:the )?(?:next|later|"
                        r"previous|last|coming) (?:chapter|class|lecture|video|session|section))\b", re.IGNORECASE)
# the speaker or the class as the subject ("You will have the basic idea ...", "We need to understand ..."); a
# generic "we" / "you" inside a statement stays ("The oxygen we breathe is produced by photosynthesis")
_SPEAKER = re.compile(r"^(?:you|we|i|your|our|imagine|consider|suppose|notice|note that|look at)\b(?!-)|"
                      r"\b(?:I'm|I've|I'll|let me|let's|let us)\b", re.IGNORECASE)
# the rest of a sentence Whisper cut off its subject or its first half: "Will come out of the cell ...", "Through
# online sales data and identify ...", "As in the solid state ..." (tests 3, 14, 15)
_FRAGMENT = re.compile(r"^(?:will|must|can|could|should|may|might|would|shall|through|to|as|or|plus|just|because|"
                       r"since|by|of|from|into|than|via|whereas)\b", re.IGNORECASE)
# a heading said straight into the next sentence: "Doping a semiconductor One way to increase ...", "Formula Mass
# Some substances ...", "... of an Operating System An operating system performs ..." (tests 3, 25, 30)
_GLUED_INSIDE = re.compile(r"[A-Za-z] (?:Some|One|The|This|These|There|It|An) [a-z]")
# a bare pronoun as the subject: on its own slide line nobody knows what "it" is ("It can involve reviewing, ...")
_VAGUE = re.compile(r"^(?:it|this|that|these|those|they|he|she)\b(?!(?:\s+\w+)?\s+(?:is|are|was|were)\s+(?:called|"
                    r"known|termed|named))", re.IGNORECASE)
# a section heading Whisper glued to its first sentence: "Economic, as a result of numerous wars ..." (test20)
_GLUED = re.compile(r"^[A-Z][a-z]+,\s+(?:as|while|during|after|due|because|since|despite)\b")


def problem(text: str, *, speaker: bool = True) -> str:
    """Why `text` (a tidied spoken sentence) must not be a slide line, or "" when it may.
    speaker=False keeps first/second-person lines (the fallback shows the teacher's examples, "If you buy the
    book, ...": with no model answer there is nothing else to show)."""
    t = " ".join(text.split())
    if _META.search(t):
        return "meta"
    if _CODE.search(t):
        return "spoken code"
    if _REFERENCE.search(t):
        return "reference"
    if speaker and _SPEAKER.search(t):
        return "speaker"
    if speaker and _VAGUE.match(t) and len(t.split()) >= 4:
        return "vague subject"
    if _GLUED.match(t) or _GLUED_INSIDE.search(t):
        return "glued heading"
    if _FRAGMENT.match(t):
        return "fragment"
    return ""


# a model item with a note about the transcript inside: "Violent crackdowns on peaceful protesters, notably at the
# [unclear location, likely mis‑heard]" (test6) -> "Violent crackdowns on peaceful protesters"
_META_PART = re.compile(r"\s*\[[^\]]*(?:unclear|mis-?heard|mis‑heard|inaudible|unknown|not clear)[^\]]*\]",
                        re.IGNORECASE)
_DANGLING = re.compile(r"(?:,?\s+(?:notably|especially|mainly|such as|like|including))?(?:\s+(?:at|in|on|of|by|to|"
                       r"from|with|for|the|a|an))*\s*[,;:]?\s*$", re.IGNORECASE)


def strip_meta(text: str) -> str:
    """A model item without its bracketed note about the transcript (and the words left dangling before it)."""
    if not _META_PART.search(text):
        return text
    return _DANGLING.sub("", _META_PART.sub("", text)).strip(" ,;:")
