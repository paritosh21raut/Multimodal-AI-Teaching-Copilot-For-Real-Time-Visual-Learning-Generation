"""DiscourseBuffer + Gate: *when* to interpret. Pure logic on lecture time (no I/O, no wall clock)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from copilot.core.textutil import approx_tokens, ends_sentence, word_count


@dataclass(frozen=True)
class BufferedLine:
    segment_id: str
    text: str
    start: float
    end: float
    maybe_meta: bool = False
    question: bool = False

    @property
    def words(self) -> int:
        return word_count(self.text)

    @property
    def tokens(self) -> int:
        return approx_tokens(self.text)


@dataclass
class GateConfig:
    pause_s: float = 1.2
    pause_min_words: int = 6       # a pause sends a unit of at least this many words ...
    long_pause_s: float = 3.0      # ... or any complete unit after a long pause
    max_words: int = 40
    max_wait_s: float = 12.0
    min_unit_words: int = 6        # max_wait holds a smaller unit (a lone fragment) for its continuation
    hold_s: float = 6.0            # bounded extra wait past max_wait for an incomplete/tiny unit
    buffer_cap_tokens: int = 600


@dataclass
class DiscourseBuffer:
    """Content lines since the last interpretation, split into units by *cuts* (concept boundaries or a
    sealed unit). Each unit is sent as its own request. Nothing is ever dropped; take() returns lines in order."""

    lines: list[BufferedLine] = field(default_factory=list)
    _cuts: list[int] = field(default_factory=list)  # ascending indices of the first line of each later unit

    def _cut_here(self) -> None:
        if self.lines and (not self._cuts or self._cuts[-1] != len(self.lines)):
            self._cuts.append(len(self.lines))

    def add(self, line: BufferedLine, boundary: bool = False) -> None:
        if boundary:
            self._cut_here()
        self.lines.append(line)

    def seal(self) -> None:
        """Close the current tail unit: lines added from now on form the next one."""
        self._cut_here()

    @property
    def empty(self) -> bool:
        return not self.lines

    @property
    def cut_pending(self) -> bool:
        return bool(self._cuts)

    def _unit(self) -> list[BufferedLine]:
        return self.lines[: self._cuts[0]] if self._cuts else self.lines

    def unit_words(self) -> int:
        return sum(l.words for l in self._unit())

    def unit_tokens(self) -> int:
        return sum(l.tokens for l in self._unit())

    def take(self, cap_tokens: int) -> list[BufferedLine]:
        """Remove and return the next unit (up to the cut), limited to cap_tokens (≥ 1 line)."""
        unit = self._unit()
        out: list[BufferedLine] = []
        used = 0
        for line in unit:
            if out and used + line.tokens > cap_tokens:
                break
            out.append(line)
            used += line.tokens
        del self.lines[: len(out)]
        self._cuts = [c - len(out) for c in self._cuts if c - len(out) > 0]
        return out


class Gate:
    def __init__(self, cfg: Optional[GateConfig] = None) -> None:
        self.cfg = cfg or GateConfig()

    def check(self, buf: DiscourseBuffer, now: float, silence_s: Optional[float] = None,
              flushing: bool = False) -> Optional[str]:
        """Reason to interpret now, or None.

        now: current lecture time. silence_s: how long the speaker has been silent (defaults to the
        time since the last buffered line ended; the live mic path passes a VAD-informed value).
        """
        if buf.empty:
            return None
        c = self.cfg
        if buf.cut_pending:
            return "boundary"
        if buf.unit_tokens() >= c.buffer_cap_tokens:
            return "cap"
        words = buf.unit_words()
        last = buf.lines[-1]
        # A unit should end where the speaker ended a sentence: a trailing fragment ("The output of this
        # process is") is held briefly for its continuation, and a lone short line is held so it is not
        # sent by itself. The hold is bounded by max_wait_s + hold_s.
        complete = ends_sentence(last.text)
        age = now - buf.lines[0].end
        overdue = age >= c.max_wait_s + c.hold_s
        if words >= c.max_words and (complete or overdue or words >= c.max_words * 1.5):
            return "words"
        if age >= c.max_wait_s and ((complete and words >= c.min_unit_words) or overdue):
            return "max_wait"
        silence = now - last.end if silence_s is None else silence_s
        if complete and silence >= c.pause_s and (words >= c.pause_min_words or silence >= c.long_pause_s):
            return "pause"
        if flushing:
            return "flush"
        return None
