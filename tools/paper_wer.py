"""Paper: word error rate of the live transcript against human captions (zero LLM tokens).

    .venv/Scripts/python tools/paper_wer.py <test> <captions.srt> <clip_start_s>   # -> verify_results/_eval/wer_<test>.json

The reference is the publisher's caption file (e.g. MIT OCW 7.016 lec 11 on archive.org), cut to the clip that was
played into the copilot (meta.json note, "clip 3:00-13:00"); speaker labels ("ADAM MARTIN:") and bracketed sound
notes are removed. Both sides are lower-cased, punctuation is dropped, hyphens split words and digits are kept as
written (Whisper writes "10", captions may write "ten": counted as errors, so the WER is conservative). The
hypothesis is every TranscriptFinal of the live session (before the meta/filler filter). Levenshtein over words.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(text: str) -> list[str]:
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"\b[A-Z][A-Z .'-]+:", " ", text)  # speaker labels
    text = text.lower().replace("-", " ").replace("’", "'")
    return re.findall(r"[a-z0-9']+", text)


def srt(path: Path) -> list[tuple[float, str]]:
    out = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="replace")):
        lines = block.strip().splitlines()
        m = next((re.match(r"(\d+):(\d+):(\d+),(\d+)", x) for x in lines if "-->" in x), None)
        if m:
            h, mi, s, ms = map(int, m.groups())
            out.append((h * 3600 + mi * 60 + s + ms / 1000, " ".join(x for x in lines if "-->" not in x
                                                                      and not x.strip().isdigit())))
    return out


def edits(ref: list[str], hyp: list[str]) -> tuple[int, int, int]:
    """(substitutions, deletions, insertions) of the minimum word alignment."""
    prev = [(j, 0, 0, j) for j in range(len(hyp) + 1)]  # cost, S, D, I
    for i in range(1, len(ref) + 1):
        cur = [(i, 0, i, 0)]
        for j in range(1, len(hyp) + 1):
            same = ref[i - 1] == hyp[j - 1]
            a = prev[j - 1]; a = (a[0] + (not same), a[1] + (not same), a[2], a[3])
            b = prev[j]; b = (b[0] + 1, b[1], b[2] + 1, b[3])
            c = cur[j - 1]; c = (c[0] + 1, c[1], c[2], c[3] + 1)
            cur.append(min(a, b, c))
        prev = cur
    return prev[-1][1:]


def main(test: str, captions: str, clip_start: float) -> None:
    db = sqlite3.connect(ROOT / "verify_results" / test / "session" / "session.sqlite")
    seg = [json.loads(p)["segment"] for (p,) in db.execute(
        "select payload from events where type='TranscriptFinal' order by seq")]
    t0, t1 = clip_start + seg[0]["start"], clip_start + seg[-1]["end"]
    ref = [w for t, x in srt(Path(captions)) if t0 - 1 <= t <= t1 for w in norm(x)]
    hyp = [w for s in seg for w in norm(s["text"])]
    s, d, i = edits(ref, hyp)
    res = dict(test=test, ref_words=len(ref), hyp_words=len(hyp), S=s, D=d, I=i, wer=round((s + d + i) / len(ref), 4),
               minutes=round((t1 - t0) / 60, 1), captions=Path(captions).name)
    out = ROOT / "verify_results" / "_eval" / f"wer_{test}.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(res)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
