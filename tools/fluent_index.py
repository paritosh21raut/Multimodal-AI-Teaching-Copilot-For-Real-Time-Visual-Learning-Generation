"""Builds the Fluent 3D emoji index (F-016 C1) for scene pictures: emoji name -> its 3D PNG path in the
microsoft/fluentui-emoji repo (MIT licence). One GitHub tree call; the PNGs are fetched on demand by scene.pictures
(through jsDelivr) and cached in data/assets/pictures/. Writes src/copilot/scene/fluent3d.json (committed).

    python tools/fluent_index.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

TREE = "https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/main?recursive=1"
OUT = Path(__file__).resolve().parents[1] / "src" / "copilot" / "scene" / "fluent3d.json"
# skin-tone variants: the "Default" one is kept
_TONE = re.compile(r"/(?:Light|Medium-Light|Medium|Medium-Dark|Dark)/")


def main() -> None:
    tree = httpx.get(TREE, timeout=120, follow_redirects=True).json()["tree"]
    out: dict[str, str] = {}
    for f in tree:
        p = f["path"]
        if not (p.startswith("assets/") and "/3D/" in p and p.endswith(".png")) or _TONE.search(p):
            continue
        name = p.split("/")[1].lower()
        out.setdefault(name, p)
    data = {"licence": "MIT, microsoft/fluentui-emoji", "base": "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/",
            "emoji": dict(sorted(out.items()))}
    OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} emoji -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
