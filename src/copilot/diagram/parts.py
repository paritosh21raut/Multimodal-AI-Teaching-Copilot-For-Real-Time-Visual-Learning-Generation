"""The diagram part library (config/diagram_parts.json, contract §2) and its tables (planets, elements, chemicals):
the only facts the diagrams print or draw."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
PARTS = ROOT / "config" / "diagram_parts.json"


@lru_cache(maxsize=1)
def library() -> dict[str, Any]:
    return json.loads(PARTS.read_text(encoding="utf-8"))


def kinds() -> dict[str, dict[str, Any]]:
    return library()["parts"]


def kind(k: str) -> Optional[dict[str, Any]]:
    return kinds().get(k)


def table(name: str) -> Any:
    return library()["tables"][name]


@lru_cache(maxsize=1)
def words() -> dict[str, str]:
    """said noun (lower case, singular) -> part kind; longer phrases first."""
    out = {w: k for k, row in kinds().items() for w in row["words"]}
    out.update({p["name"].lower(): "planet" for p in table("planets")})
    return dict(sorted(out.items(), key=lambda kv: -len(kv[0])))


def planet(name: str) -> Optional[dict[str, Any]]:
    return next((p for p in table("planets") if p["name"].lower() == name.lower()), None)


def element(word: str) -> Optional[tuple[int, str, str]]:
    """(Z, name, symbol) of an element name or symbol (Z <= 20, the K1 table)."""
    w = word.strip()
    names, syms = table("elements"), table("symbols")
    if w.lower() in names:
        z = names.index(w.lower()) + 1
    elif w in syms:
        z = syms.index(w) + 1
    else:
        return None
    return z, names[z - 1], syms[z - 1]


def shells(z: int) -> list[int]:
    """Electrons per shell, the school rule for Z <= 20 (2, 8, 8, 2)."""
    out, left = [], z
    for cap in table("shell_caps"):
        if left <= 0:
            break
        out.append(min(cap, left))
        left -= cap
    return out


@lru_cache(maxsize=1)
def chemicals() -> dict[str, str]:
    """said chemical word (lower case) -> chemical id; longer first."""
    out = {w: cid for cid, row in table("chemicals").items() for w in row["words"]}
    return dict(sorted(out.items(), key=lambda kv: -len(kv[0])))


def chemical(cid: str) -> Optional[dict[str, Any]]:
    return table("chemicals").get(cid)
