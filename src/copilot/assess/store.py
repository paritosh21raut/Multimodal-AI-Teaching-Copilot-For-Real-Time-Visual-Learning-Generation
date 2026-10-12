"""Quizzes and tests kept with their lecture (F-011): data/assessments/<id>.json, written atomically.

Every assessment is one file (questions with keys, participants with tokens and answers, results). The Lectures tab
lists a lecture's assessments by `lecture_id`; results also export as CSV. Never served to students as a file.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from copilot.assess.model import Assessment

log = logging.getLogger(__name__)

_ID = re.compile(r"[\w-]{1,64}")


class AssessmentStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    def path(self, aid: str) -> Optional[Path]:
        return self.root / f"{aid}.json" if _ID.fullmatch(aid or "") else None

    def save(self, a: Assessment) -> None:
        path = self.path(a.id)
        assert path is not None, a.id
        data = a.model_dump_json()
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(data, encoding="utf-8")
            os.replace(tmp, path)

    def load(self, aid: str) -> Optional[Assessment]:
        path = self.path(aid)
        if path is None or not path.is_file():
            return None
        try:
            return Assessment.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("assessment %s unreadable: %s", aid, e)
            return None

    def for_lecture(self, lecture_id: str) -> list[Assessment]:
        """The quizzes / tests run in (or made from) this lecture, newest first; drafts never opened are left out."""
        out = []
        if not self.root.is_dir():
            return out
        for path in self.root.glob("*.json"):
            a = self.load(path.stem)
            if a is not None and a.status in ("running", "finished") and \
                    (a.lecture_id == lecture_id or lecture_id in a.sources):
                out.append(a)
        return sorted(out, key=lambda a: -a.created)


def summary(a: Assessment) -> dict[str, Any]:
    """One row in the Lectures tab."""
    return {"id": a.id, "kind": a.kind, "title": a.title, "status": a.status, "created": a.created,
            "questions": len(a.questions), "students": len(a.participants), "lecture_id": a.lecture_id}


def results_csv(a: Assessment) -> str:
    """The results table as in /control (quiz: points, score x/n, average response time; test: score, time taken),
    then one column per question (the option letter chosen)."""
    out = io.StringIO()
    w = csv.writer(out)
    qs = a.questions
    if a.kind == "quiz":
        head = ["Rank", "Name", "Roll no.", "Points", "Score", "Answered", "Avg. response time (s)"]
    else:
        head = ["Rank", "Name", "Roll no.", "Score", "Answered", "Time taken", "Submitted", "Auto-submitted"]
    w.writerow(head + [f"Q{n}" for n in range(1, len(qs) + 1)])
    by_roll = {p.roll: p for p in a.participants.values()}
    board = a.leaderboard(a.closed_questions() if a.kind == "quiz" else None)
    for r in board:
        p = by_roll[r["roll"]]
        row: list[Any] = [r["rank"], r["name"], r["roll"]]
        if a.kind == "quiz":
            row += [r["score"], f"{r['correct']}/{r['asked']}", r["answered"], "" if r["avg"] is None else r["avg"]]
        else:
            row += [f"{r['score']}/{r['total']}", r["answered"], duration(r["taken"]),
                    datetime.fromtimestamp(p.submitted).strftime("%H:%M:%S") if p.submitted else "",
                    "yes" if p.auto else ""]
        for q in qs:
            ans = p.answers.get(q.id)
            row.append("" if ans is None else "ABCD"[ans.choice] + ("" if ans.choice == q.answer else " (x)"))
        w.writerow(row)
    w.writerow([])
    w.writerow(["Key"] + [""] * (len(head) - 1) + ["ABCD"[q.answer] for q in qs])
    return out.getvalue()


def duration(seconds: Optional[float]) -> str:
    """'12:05' (minutes:seconds); '' when not submitted."""
    if seconds is None:
        return ""
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def csv_name(a: Assessment) -> str:
    d = datetime.fromtimestamp(a.created) if a.created else datetime.now()
    title = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", a.title or "Lecture").strip(" .")[:80] or "Lecture"
    return f"{title} - {'Quiz' if a.kind == 'quiz' else 'Test'} results - {d.day} {d:%b %Y}.csv"
