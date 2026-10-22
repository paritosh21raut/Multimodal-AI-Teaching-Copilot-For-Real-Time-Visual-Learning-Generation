"""The canvas's safety filter (F-016 §6, 0 tokens): a word blocklist on the teacher's lines and on every noun the model
asks to draw. A blocked line is not sent to the model; a blocked noun is never drawn (logged). The model's own
`unsafe` op catches what the list misses; picture search keeps its safe-search filters (scene.pictures).

Decided with the user (2026-10-22): sexual content, gore and graphic violence, slurs, self-harm and drug use are
blocked; physics words (gun, bullet, cannon, bomb, explosion) are allowed: they are classroom physics, and so are
classroom words that a violent sense shares (blood, kill bacteria, program execution, retarded motion, the naked
eye)."""
from __future__ import annotations

import re

# whole words (a plural / -ing / -ed form counts); kept short and unambiguous so physics talk is never blocked
_BLOCK = (
    # sexual content
    "sex", "sexy", "sexual", "porn", "porno", "pornography", "nude", "nudes", "nipple", "genitals", "penis",
    "vagina", "boob", "boobs", "orgasm", "erotic", "fetish", "stripper", "hooker", "prostitute", "masturbate",
    "condom", "dildo", "rape", "rapist", "molest", "incest",
    # gore and graphic violence
    "bloody", "gore", "gory", "corpse", "corpses", "dead body", "dismember", "decapitate", "behead",
    "mutilate", "disembowel", "murder", "murderer", "stab", "stabbing", "slaughter", "massacre",
    "torture", "suicide bomber", "terrorist", "shoot someone", "shooting people",
    # self-harm
    "suicide", "self harm", "self-harm", "cut myself", "hang myself", "overdose",
    # drugs
    "cocaine", "heroin", "meth", "methamphetamine", "crack pipe", "marijuana", "cannabis", "lsd",
    "ecstasy", "inject drugs", "syringe of drugs",
    # slurs (a small set; the model's unsafe op covers the rest)
    "nigger", "nigga", "faggot", "fag", "spic", "kike", "tranny", "whore", "slut",
    "bitch",
)
_RX = re.compile(r"\b(?:" + "|".join(re.escape(w).replace(r"\ ", r"[\s-]+") for w in sorted(_BLOCK, key=len,
                                                                                            reverse=True))
                 + r")(?:s|es|ing|ed|ers?)?\b", re.IGNORECASE)


def blocked(text: str) -> str:
    """The first blocked word in `text`, or ""."""
    m = _RX.search(text or "")
    return m.group(0).lower() if m else ""
