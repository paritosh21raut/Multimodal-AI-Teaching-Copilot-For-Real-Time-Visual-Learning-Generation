from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.importance.importance_types import (
    Centrality,
    DevelopmentalRole,
    Emphasis,
)


# ----------------------------------------------------------
# EXPLICIT EMPHASIS
# ----------------------------------------------------------
#
# Narrow, high-precision phrase set. First match in the chunk wins.
# Evidence is the verbatim phrase (lowercased, normalized spacing).
# ----------------------------------------------------------

_EMPHASIS_PHRASES: Tuple[str, ...] = (
    "remember this",
    "remember that",
    "most importantly",
    "most important",
    "this is very important",
    "this is important",
    "this is the key point",
    "the key point is",
    "key point",
    "pay attention to this",
    "pay close attention to",
    "pay attention",
    "keep this in mind",
    "an important property is",
    "another important property",
    "important property",
    "do not forget",
    "don't forget",
    "make sure you understand",
    "make sure you remember",
)


def detect_explicit_emphasis(text: str) -> Tuple[str, Optional[str]]:
    """
    Returns (Emphasis value, verbatim evidence phrase or None).

    YES only when a clear emphasis phrase is present.
    NO otherwise.
    UNCERTAIN only for empty input.
    """
    if not text or not text.strip():
        return Emphasis.UNCERTAIN.value, None

    lowered = " ".join(text.lower().split())

    for phrase in _EMPHASIS_PHRASES:
        if phrase in lowered:
            return Emphasis.YES.value, phrase

    return Emphasis.NO.value, None


# ----------------------------------------------------------
# DEVELOPMENTAL ROLE PATTERNS (high-precision)
# ----------------------------------------------------------
#
# Cue lists per role. Cues ending with a space are matched as prefixes
# or at a word boundary. Other cues are matched with a word-boundary
# regex to prevent substring false positives.
# ----------------------------------------------------------

_INTRO_FRAMING_PHRASES: Tuple[str, ...] = (
    "we will learn about",
    "we will discuss",
    "we will study",
    "we are going to learn",
    "we're going to learn",
    "we'll learn about",
    "we will look at",
    "today we will learn",
    "today we will discuss",
    "today we will study",
    "today we'll learn",
    "today we'll discuss",
    "let's discuss",
    "let us discuss",
    "let's talk about",
    "let us talk about",
    "now let's learn about",
    "now let us learn about",
    "now we will learn",
    "now we'll learn",
    "now let's look at",
    "now let us look at",
    "now let's discuss",
    "now we discuss",
)


_ROLE_CUES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        DevelopmentalRole.META.value,
        (
            "let's move on",
            "let us move on",
            "now let's move",
            "next topic",
            "next section",
            "as mentioned earlier",
            "as we discussed",
            "let's take a break",
            "let's take a short break",
            "by the way",
            "the exam",
            "exam covers",
            "exam will",
            "no need to memorize",
            "remember what we discussed",
            "you may have seen",
            "check the projector",
        ),
    ),
    (
        DevelopmentalRole.EXCEPTION.value,
        (
            "except when",
            "except if",
            "unless ",
            "does not apply when",
            "does not hold when",
            "however, in this case",
        ),
    ),
    (
        DevelopmentalRole.SYNTHESIS.value,
        (
            "in summary",
            "to summarize",
            "summarizing",
            "putting these together",
            "putting this together",
            "putting together",
            "overall,",
            "in conclusion",
            "therefore,",
        ),
    ),
    (
        DevelopmentalRole.PROCEDURE.value,
        (
            "first,",
            "first ",
            "then,",
            "then ",
            "next,",
            "next ",
            "finally,",
            "finally ",
        ),
    ),
    (
        DevelopmentalRole.EXAMPLE.value,
        (
            "for example",
            "for instance",
            "such as",
            "consider a ",
            "consider an ",
            "consider the ",
        ),
    ),
    (
        DevelopmentalRole.APPLICATION.value,
        (
            "used in",
            "used for",
            "used to",
            "is used",
            "are used",
            "applied in",
            "applied to",
            "you can find",
            "you will find",
        ),
    ),
    (
        DevelopmentalRole.DEFINITION.value,
        (
            "is defined as",
            "are defined as",
            "is called",
            "are called",
            "refers to",
            "refer to",
            "means ",
            "stands for",
            "stand for",
        ),
    ),
    (
        DevelopmentalRole.RELATIONSHIP.value,
        (
            "related to",
            "depends on",
            "leads to",
            "connected to",
            "in contrast",
            "by contrast",
            "unlike ",
            "compared to",
            "compared with",
            "relationship between",
        ),
    ),
    (
        DevelopmentalRole.MECHANISM.value,
        (
            "works by",
            "operates by",
            "because ",
            "due to",
            "caused by",
            "consists of",
            "contains ",
            "is composed of",
            "happens when",
        ),
    ),
    (
        DevelopmentalRole.PROPERTY.value,
        (
            "is a ",
            "is an ",
            "are a ",
            "has ",
            "have ",
            "characterized by",
            "property is",
            "properties are",
            "opposes ",
            "stores ",
            "blocks ",
            "passes ",
        ),
    ),
)


def _has_word_boundary_cue(lowered: str, cue: str) -> bool:
    """
    Match cue at a word boundary. Used for cues not ending in a space.
    """
    pattern = (
        r"(?:^|[\s,;:.!?()\[\]{}\-])"
        + re.escape(cue)
        + r"(?:$|[\s,;:.!?()\[\]{}\-])"
    )
    return re.search(pattern, lowered) is not None


def _has_any(lowered: str, cues: Tuple[str, ...]) -> bool:
    for cue in cues:
        if cue.endswith(" "):
            if lowered.startswith(cue) or f" {cue}" in lowered:
                return True
        else:
            if _has_word_boundary_cue(lowered, cue):
                return True
    return False


def _has_intro_framing(lowered: str) -> bool:
    return any(p in lowered for p in _INTRO_FRAMING_PHRASES)


def _has_definition_cue(lowered: str) -> bool:
    definition_cues = (
        "is defined as",
        "are defined as",
        "is called",
        "are called",
        "refers to",
        "refer to",
        "stands for",
        "stand for",
    )
    return any(cue in lowered for cue in definition_cues)


def detect_developmental_roles(
    text: str,
    *,
    lsi_relation: Optional[str] = None,
) -> List[str]:
    """
    Multilabel. High-precision cue matching plus optional LSI structural
    context for INTRODUCTION.

    INTRODUCTION fires when:
    - explicit framing phrase present, OR
    - LSI relation is new_topic/subtopic AND text carries substantive
      assertion content (not a pure meta transition).

    META transitions still take precedence for their own label; a chunk
    can carry both META and INTRODUCTION if the framing is genuinely
    about both.
    """
    if not text or not text.strip():
        return [DevelopmentalRole.UNKNOWN.value]

    lowered = " ".join(text.lower().split())

    hits: List[str] = []

    if _has_intro_framing(lowered):
        hits.append(DevelopmentalRole.INTRODUCTION.value)
    elif lsi_relation in ("new_topic", "subtopic"):
        # LSI says new structure. Only promote to INTRODUCTION when the
        # chunk carries real assertion content, not pure lecture management.
        meta_only = _has_any(lowered, dict(_ROLE_CUES)[DevelopmentalRole.META.value])
        if not meta_only and len(lowered.split()) >= 5:
            hits.append(DevelopmentalRole.INTRODUCTION.value)

    for role, cues in _ROLE_CUES:
        if _has_any(lowered, cues):
            hits.append(role)

    order = [
        DevelopmentalRole.INTRODUCTION.value,
        DevelopmentalRole.DEFINITION.value,
        DevelopmentalRole.PROPERTY.value,
        DevelopmentalRole.RELATIONSHIP.value,
        DevelopmentalRole.MECHANISM.value,
        DevelopmentalRole.PROCEDURE.value,
        DevelopmentalRole.EXAMPLE.value,
        DevelopmentalRole.APPLICATION.value,
        DevelopmentalRole.EXCEPTION.value,
        DevelopmentalRole.SYNTHESIS.value,
        DevelopmentalRole.META.value,
        DevelopmentalRole.UNKNOWN.value,
    ]
    seen = set(hits)
    ordered = [r for r in order if r in seen]

    if not ordered:
        return [DevelopmentalRole.UNKNOWN.value]
    return ordered


# ----------------------------------------------------------
# STRUCTURAL CENTRALITY
# ----------------------------------------------------------

_META_CUES: Tuple[str, ...] = (
    "let's move on",
    "let us move on",
    "now let's move",
    "let's take a break",
    "let's take a short break",
    "by the way",
    "next topic",
    "next section",
    "the exam",
    "exam covers",
    "no need to memorize",
    "check the projector",
    "lab manual uses",
    "lab uses",
    "lab provides",
    "lab session",
    "lab demo",
    "lab equipment",
    "building closes",
    "you may have seen",
)

_LAB_DETAIL_CUES: Tuple[str, ...] = (
    "10 microfarad",
    "10 µf",
    "10 uf",
    "second bench",
    "front bench",
    "specific stm32",
    "different default port",
    "torque wrenches",
    "wireshark",
    "small dc motor",
)

_CONTINUATION_LSI_RELATIONS = frozenset(
    {"continuation", "detail", "related", "return"}
)


def _is_meta(lowered: str) -> bool:
    return any(cue in lowered for cue in _META_CUES)


def _is_lab_detail(lowered: str) -> bool:
    return any(cue in lowered for cue in _LAB_DETAIL_CUES)


def classify_structural_centrality(
    *,
    text: str,
    concept_label: Optional[str],
    concept_first_seen: bool,
    concept_mention_count: int,
    prior_assertions_for_concept: Tuple[str, ...],
    lsi_relation: Optional[str],
    lsi_node_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Returns (Centrality value, reason string).

    Architect decision B:
    - CORE: introduces a concept new at the current instructional level, or
      gives the initial definition of the concept currently being developed.
    - SUPPORTING: develops, elaborates, refines, corrects, explains,
      justifies, or illustrates an already introduced concept.
    - INCIDENTAL: mentioned in passing, not materially developed, not
      needed for coherence.
    - UNCERTAIN: insufficient evidence to decide safely.

    Decision order (conservative):
    1. Meta / lab detail / LSI-irrelevant -> INCIDENTAL.
    2. High-precision definition cue OR explicit intro framing AND LSI says
       new structure -> CORE.
    3. LSI new_topic/subtopic with substantive content and no definition cue
       -> CORE only when concept is genuinely new (first mention AND no
       prior assertions AND not in a continuation relation).
    4. Continuation/detail/related/return + no strong new-concept cue
       -> SUPPORTING.
    5. Concept with prior assertions -> SUPPORTING.
    6. Insufficient evidence -> UNCERTAIN.

    The weak path "string label not in ledger -> CORE" is NOT used.
    `concept_first_seen` alone is insufficient for CORE.
    """
    if not text or not text.strip():
        return Centrality.UNCERTAIN.value, "empty_text"

    lowered = " ".join(text.lower().split())

    # 1. Incidental / meta.
    if _is_meta(lowered):
        return Centrality.INCIDENTAL.value, "meta_statement"
    if _is_lab_detail(lowered):
        return Centrality.INCIDENTAL.value, "lab_detail"
    if lsi_relation == "irrelevant":
        return Centrality.INCIDENTAL.value, "lsi_irrelevant"

    definition_cue = _has_definition_cue(lowered)
    intro_framing = _has_intro_framing(lowered)
    in_continuation = lsi_relation in _CONTINUATION_LSI_RELATIONS
    is_new_structure = lsi_relation in ("new_topic", "subtopic", "sibling")

    # 2. High-precision definition cue -> CORE.
    if definition_cue:
        return Centrality.CORE.value, "definition_cue"

    # 2b. Explicit intro framing when LSI says new structure -> CORE.
    if intro_framing and is_new_structure:
        return Centrality.CORE.value, "intro_framing_on_new_structure"

    # 3. LSI new structure, substantive content, no continuation relation.
    #    Only CORE when the concept really is new: first mention AND no
    #    prior assertions. Any of those failing pushes toward SUPPORTING.
    if is_new_structure and not in_continuation:
        has_prior = bool(prior_assertions_for_concept)
        if (
            concept_label
            and concept_first_seen
            and not has_prior
            and concept_mention_count <= 1
        ):
            return Centrality.CORE.value, "new_structure_new_concept"

    # 4. Continuation with no strong new-concept cue -> SUPPORTING.
    if in_continuation:
        return Centrality.SUPPORTING.value, "lsi_continuation"

    # 5. Concept has prior assertions -> SUPPORTING.
    if concept_label and prior_assertions_for_concept:
        return Centrality.SUPPORTING.value, "develops_existing_concept"

    # 6. Insufficient evidence.
    return Centrality.UNCERTAIN.value, "insufficient_local_evidence"


def confidence_for(
    *,
    centrality: str,
    roles: List[str],
    emphasis: str,
) -> float:
    """
    Internal heuristic confidence, NOT a calibrated probability.
    """
    score = 0.5
    if centrality == Centrality.CORE.value:
        score += 0.2
    elif centrality == Centrality.SUPPORTING.value:
        score += 0.15
    elif centrality == Centrality.INCIDENTAL.value:
        score += 0.15
    else:
        score -= 0.1

    if roles and DevelopmentalRole.UNKNOWN.value not in roles:
        score += 0.1

    if emphasis == Emphasis.YES.value:
        score += 0.05

    return round(max(0.0, min(1.0, score)), 3)