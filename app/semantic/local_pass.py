from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.semantic.semantic_types import (
    InformationType,
    LocalExtraction,
    SentenceSpan,
)


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# ----------------------------------------------------------
# NARROW RESOLVER (Experiment B B2 + B27 guard)
# ----------------------------------------------------------

DEFINITION_CUES: Tuple[str, ...] = (
    "is defined as",
    "are defined as",
    "is called",
    "are called",
    "refers to",
    "refer to",
    "means",
)

ALIAS_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"^(.+?),\s+also\s+called\s+(.+?)(?:,|$)", re.IGNORECASE),
    re.compile(r"^(.+?),\s+also\s+known\s+as\s+(.+?)(?:,|$)", re.IGNORECASE),
    re.compile(r"^(.+?),\s+or\s+(.+?)(?:,|$)", re.IGNORECASE),
)

FORMULA_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9' ]{0,40}?)\s*=\s*([A-Za-z0-9' ]+?)\s*[.!?]?$"
)

ENUM_HEAD_RE = re.compile(
    r"^(?:The|A|An)\s+([A-Za-z][A-Za-z0-9' -]{0,40}?)\s+"
    r"(is|are)\s+"
    r"([A-Za-z][A-Za-z0-9' -]+"
    r"(?:,\s+[A-Za-z][A-Za-z0-9' -]+)+"
    r",?\s+(?:and|or)\s+"
    r"[A-Za-z][A-Za-z0-9' -]+)"
    r"\s*[.!?]?$",
    re.IGNORECASE,
)

_DISALLOWED_LEADING_TOKENS = {
    "which", "who", "whom", "whose", "that", "it", "this", "these",
    "those", "there", "here", "and", "but", "or", "so", "if", "when",
    "where", "while", "although", "because",
}

_FORMULA_LHS_FORBIDDEN_TOKENS = {
    "is", "are", "was", "were", "be", "been", "being",
    "that", "which", "the", "a", "an", "this", "these", "those",
    "there", "it", "and", "or", "but", "if", "then", "than",
    "as", "by", "of", "for", "in", "on", "at", "to", "from", "with",
    "has", "have", "had", "does", "do", "did",
}


def _clean(s: str) -> str:
    return " ".join(s.strip().split()).strip(" .,;:")


def _starts_with_disallowed(s: str) -> bool:
    tokens = s.strip().lower().split()
    if not tokens:
        return True
    return tokens[0].strip(".,;:") in _DISALLOWED_LEADING_TOKENS


def _lhs_looks_like_prose(lhs: str) -> bool:
    tokens = [t.strip(".,;:!?").lower() for t in lhs.split()]
    return any(tok in _FORMULA_LHS_FORBIDDEN_TOKENS for tok in tokens)


def split_sentences(text: str) -> List[SentenceSpan]:
    """
    Deterministic sentence splitting. Local implementation used by Phase 4.
    Phase 2's splitter remains untouched.
    """
    if not text or not text.strip():
        return []

    normalized = " ".join(text.split())

    spans: List[SentenceSpan] = []
    cursor = 0

    # We split on sentence terminators, then locate each part in the
    # normalized text to compute character offsets.
    parts = _SENTENCE_SPLIT_RE.split(normalized.strip())

    for idx, part in enumerate(parts):
        cleaned = part.strip()
        if not cleaned:
            continue
        start = normalized.find(cleaned, cursor)
        if start < 0:
            start = cursor
        end = start + len(cleaned)
        cursor = end
        spans.append(
            SentenceSpan(
                index=idx,
                text=cleaned,
                start=start,
                end=end,
            )
        )

    # Re-index sequentially to guarantee 0..n-1
    return [
        SentenceSpan(
            index=i,
            text=s.text,
            start=s.start,
            end=s.end,
        )
        for i, s in enumerate(spans)
    ]


def resolve_local(sentence: str) -> LocalExtraction:
    """
    Narrow, high-precision deterministic resolver.

    Returns LocalExtraction(action="RESOLVE", ...) when the sentence
    matches a supported pattern; otherwise action="ABSTAIN".
    """

    s = _clean(sentence)

    if not s or len(s.split()) < 2 or s.endswith("?"):
        return LocalExtraction(action="ABSTAIN")

    lower = s.lower()

    # 1) FORMULA with prose guard
    m = FORMULA_RE.match(s)
    if m:
        lhs = _clean(m.group(1))
        rhs = _clean(m.group(2))
        if (
            lhs
            and rhs
            and len(lhs.split()) <= 6
            and not _starts_with_disallowed(lhs)
            and not _lhs_looks_like_prose(lhs)
        ):
            return LocalExtraction(
                action="RESOLVE",
                kind="formula",
                subject=lhs,
                object_=f"{lhs} = {rhs}",
                predicate="expressed_as",
                information_type=InformationType.FORMULA.value,
            )

    # 2) DEFINITION cue phrases
    for cue in DEFINITION_CUES:
        idx = lower.find(f" {cue} ")
        if idx < 0:
            if lower.startswith(cue + " "):
                idx = -1
            else:
                continue

        if idx == -1:
            continue

        subject = _clean(s[:idx])
        object_ = _clean(s[idx + len(cue) + 2:])

        if not subject or not object_:
            continue
        if _starts_with_disallowed(subject):
            continue
        if len(subject.split()) > 10 or len(object_.split()) > 25:
            continue

        predicate = "defined_as"
        if "is called" in cue or "are called" in cue:
            predicate = "is_called"

        return LocalExtraction(
            action="RESOLVE",
            kind="definition",
            subject=subject,
            object_=object_,
            predicate=predicate,
            information_type=InformationType.DEFINITION.value,
        )

    # 3) ALIAS
    for r in ALIAS_PATTERNS:
        m = r.match(s)
        if m:
            a = _clean(m.group(1))
            b = _clean(m.group(2))
            if (
                a and b
                and not _starts_with_disallowed(a)
                and len(a.split()) <= 8
                and len(b.split()) <= 8
            ):
                return LocalExtraction(
                    action="RESOLVE",
                    kind="alias",
                    subject=a,
                    object_=b,
                    predicate="alias_of",
                    information_type=InformationType.DEFINITION.value,
                )

    # 4) CLOSED ENUMERATION
    m = ENUM_HEAD_RE.match(s)
    if m:
        head = _clean(m.group(1))
        items = _clean(m.group(3))
        if (
            head
            and items
            and not _starts_with_disallowed(head)
            and items.count(",") >= 1
        ):
            return LocalExtraction(
                action="RESOLVE",
                kind="enumeration",
                subject=head,
                object_=items,
                predicate="consists_of",
                information_type=InformationType.CLASSIFICATION.value,
            )

    return LocalExtraction(action="ABSTAIN")


def resolve_local_in_sentence_spans(
    spans: List[SentenceSpan],
) -> Optional[LocalExtraction]:
    """
    Try the local resolver across the sentence spans of a chunk.
    Return the FIRST local RESOLVE found, otherwise None.
    """
    for span in spans:
        extraction = resolve_local(span.text)
        if extraction.action == "RESOLVE":
            return extraction
    return None