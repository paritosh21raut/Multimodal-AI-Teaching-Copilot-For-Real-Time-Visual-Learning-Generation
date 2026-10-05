"""Concern hold-back (F-005): which content waits for the teacher, and what each decision releases. Pure.

Rules (review fixes):
- A piece is held while ANY concern linked to it is open; it is released only when all are resolved, and each
  resolution transforms it (accept → corrected, keep → as said, dismiss → the disputed text removed).
- Only the disputed text is held when it can be identified: in a list (points/steps/examples) the texts that match
  the claim are held, the others are shown at once. If no text matches, the whole piece is held (safe side).
- A concern without usable line numbers is linked to the piece that best matches its claim, or to every piece of
  the interpretation when nothing matches (nothing doubtful may slip through to the projector).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Literal, Optional

from copilot.presentation.composer import is_duplicate
from copilot.presentation.content import Piece, clean

Status = Literal["open", "accepted", "kept", "dismissed"]
LIST_KINDS = ("points", "steps", "example")
TEXT_MATCH = 0.5      # share of the shorter text's content words found in the claim
WEAK_MATCH = 0.3      # enough to pick the piece for a concern without lines
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "and", "for", "are", "is", "was", "that", "this", "with", "from", "into", "they", "their", "its",
         "during", "of", "to", "in", "a", "an", "on", "by", "as", "it", "be"}


@dataclass(frozen=True)
class ConcernInfo:
    id: str
    kind: str
    claim: str
    correction: str
    lines: frozenset[int] = frozenset()


@dataclass
class HeldPiece:
    piece: Piece
    pending: set[str] = field(default_factory=set)  # open concern ids


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


def claim_match(text: str, claim: str) -> float:
    if is_duplicate(text, claim):
        return 1.0
    a, b = _words(text), _words(claim)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _piece_match(p: Piece, claim: str) -> float:
    return max((claim_match(t, claim) for t in p.all_text()), default=0.0)


def split(pieces: list[Piece], concerns: list[ConcernInfo]) -> tuple[list[Piece], list[HeldPiece]]:
    """Shown pieces (in order) and held pieces with the concern ids they wait for."""
    pieces = list(pieces)
    for c in concerns:  # the model flagged a statement but extracted no content for it: hold the statement itself
        unlinked = (not pieces) or (bool(c.lines) and not any(c.lines & set(p.lines) for p in pieces)
                                    and not any(_piece_match(p, c.claim) >= WEAK_MATCH for p in pieces))
        if c.kind == "factual" and unlinked:
            pieces.append(Piece("points", lines=tuple(sorted(c.lines)), texts=(clean(c.claim),)))
    links: list[set[str]] = [set() for _ in pieces]
    for c in concerns:
        hits = [i for i, p in enumerate(pieces) if c.lines and set(p.lines) & c.lines]
        if not hits and pieces:
            scores = [_piece_match(p, c.claim) for p in pieces]
            best = max(range(len(pieces)), key=lambda i: scores[i])
            hits = [best] if scores[best] >= WEAK_MATCH else list(range(len(pieces)))
        for i in hits:
            links[i].add(c.id)
    by_id = {c.id: c for c in concerns}
    shown: list[Piece] = []
    held: list[HeldPiece] = []
    for p, ids in zip(pieces, links):
        if not ids:
            shown.append(p)
            continue
        if p.kind in LIST_KINDS and len(p.texts) > 1:
            per_text = [{cid for cid in ids if claim_match(t, by_id[cid].claim) >= TEXT_MATCH} for t in p.texts]
            unmatched = ids - set().union(*per_text)
            if unmatched:  # a concern that matches no text: its target is unknown, hold the rest under it
                per_text = [m or set(unmatched) for m in per_text]
            free = [t for t, m in zip(p.texts, per_text) if not m]
            if free:
                shown.append(p.with_texts(free))
            groups: dict[frozenset[str], list[str]] = {}
            for t, m in zip(p.texts, per_text):
                if m:
                    groups.setdefault(frozenset(m), []).append(t)
            held += [HeldPiece(p.with_texts(ts), set(m)) for m, ts in groups.items()]
        else:
            held.append(HeldPiece(p, set(ids)))
    return shown, held


def _strip_coeff(tok: str) -> str:
    return tok.lstrip("0123456789")


def replace_spoken(text: str, said: str, correction: str) -> str:
    """Replace a spoken token/phrase at word boundaries only (never inside a longer token)."""
    if not said or not text:
        return text
    return re.sub(rf"(?<![A-Za-z0-9]){re.escape(said)}(?![A-Za-z0-9])", correction, text)


def resolve(piece: Piece, c: ConcernInfo, status: Status) -> Optional[Piece]:
    """Apply one teacher decision to a held piece. None → nothing of it is shown."""
    if status == "kept" or status == "open":
        return piece
    if c.kind == "transcription":
        if status == "accepted" and c.correction:
            said, corr = c.claim.strip(), c.correction.strip()
            fixed = piece.map_text(lambda t: replace_spoken(t, said, corr))
            bare_said, bare_corr = _strip_coeff(said), _strip_coeff(corr)
            if bare_said and bare_said != said and bare_corr:  # derived symbol: "H2" -> "H2O" for "6H2" -> "6H2O"
                fixed = fixed.map_text(lambda t: replace_spoken(t, bare_said, bare_corr))
            return fixed
        if status == "dismissed":
            return None if any(replace_spoken(t, c.claim.strip(), "\0") != t for t in piece.all_text()) else piece
        return piece
    # factual
    if piece.kind in LIST_KINDS and piece.texts:
        idx = max(range(len(piece.texts)), key=lambda i: claim_match(piece.texts[i], c.claim))
        texts = list(piece.texts)
        if status == "accepted" and c.correction:
            texts[idx] = clean(c.correction)
        elif status == "dismissed":
            del texts[idx]
        return piece.with_texts(texts) if texts else None
    if status == "accepted" and c.correction:
        return Piece("points", lines=piece.lines, texts=(clean(c.correction),))
    if status == "dismissed":
        return None
    return piece


def apply_known(h: HeldPiece, concerns: dict[str, ConcernInfo], statuses: dict[str, Status]) -> Optional[HeldPiece]:
    """Apply decisions already made (e.g. resolved before the engine saw the interpretation)."""
    piece: Optional[Piece] = h.piece
    for cid in sorted(h.pending):
        st = statuses.get(cid, "open")
        if st != "open" and piece is not None:
            piece = resolve(piece, concerns[cid], st)
            h.pending.discard(cid)
    return replace(h, piece=piece) if piece is not None else None
