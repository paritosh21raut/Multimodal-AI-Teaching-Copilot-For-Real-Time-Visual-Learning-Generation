"""Bake the CC0 mannequin clips (Quaternius UAL1+2) into the stage's motion pack (F-017 §4).

    .venv/Scripts/python tools/stage/bake_motion.py            # bake in Edge -> web/stage/data/motion.json + table
    .venv/Scripts/python tools/stage/bake_motion.py --table    # only rebuild config/stage_clips.json

The bake reads data/assets/stage/src/ual{1,2}.zip (CC0), unpacks the two files rig.js loads into
artifacts/stage/bake/, and runs rig.js there with three.js r160 (vendor/: three.module.min.js + jsm/loaders, taken
from artifacts/v2look/vendor or --three <dir>). The clip table (loop, verbs, stride speed, events, seat / hand
heights, foot contacts and lock) comes from copilot.stage.motion.clip_table.
"""
import argparse
import functools
import http.server
import json
import shutil
import sys
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from copilot.stage.motion import CLIPS, MOTION, clip_table, load  # noqa: E402

SRC = ROOT / "data" / "assets" / "stage" / "src"
WORK = ROOT / "artifacts" / "stage" / "bake"
UNPACK = {  # zip -> (member, file name rig.js loads)
    "ual2.zip": ("Universal Animation Library 2 [Standard]/Unreal-Godot/UAL2_Standard.glb", "ual2.glb"),
    "ual1.zip": ("Animation Library[Standard]/Unreal Engine/AL_Standard.fbx", "ual1_ue.fbx"),
}


def prepare(three: Path) -> None:
    (WORK / "assets" / "ual").mkdir(parents=True, exist_ok=True)
    for z, (member, name) in UNPACK.items():
        out = WORK / "assets" / "ual" / name
        if not out.exists():
            with zipfile.ZipFile(SRC / z) as zf, zf.open(member) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    if not (WORK / "vendor").exists():
        if not (three / "three.module.min.js").exists():
            sys.exit(f"three.js r160 not found in {three} (needs three.module.min.js and jsm/loaders); pass --three")
        shutil.copytree(three, WORK / "vendor")
    for f in ("rig.js", "bake.html"):
        shutil.copy(ROOT / "tools" / "stage" / f, WORK / f)


def bake() -> dict:
    from playwright.sync_api import sync_playwright

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    h = functools.partial(Quiet, directory=str(WORK))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="msedge", headless=True)
            page = b.new_page()
            page.on("console", lambda m: m.type == "error" and "favicon" not in m.text and print("console:", m.text))
            page.goto(f"http://127.0.0.1:{srv.server_address[1]}/bake.html")
            page.wait_for_function("document.title!=='bake'", timeout=300000)
            if page.title() != "done":
                sys.exit(page.title())
            r = page.evaluate("window.__bake")
            b.close()
    finally:
        srv.shutdown()
    return {"joints": r["joints"], "fps": r["fps"], "clips": r["clips"]}  # the bone list is not needed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="store_true", help="only rebuild the clip table from the committed motion.json")
    ap.add_argument("--three", type=Path, default=ROOT / "artifacts" / "v2look" / "vendor")
    a = ap.parse_args()
    if not a.table:
        prepare(a.three)
        data = bake()
        MOTION.parent.mkdir(parents=True, exist_ok=True)
        MOTION.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print("wrote", MOTION.relative_to(ROOT), MOTION.stat().st_size // 1024, "KB,", len(data["clips"]), "clips")
    table = clip_table(load(MOTION))
    CLIPS.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    print("wrote", CLIPS.relative_to(ROOT), len(table["clips"]), "rows")


if __name__ == "__main__":
    main()
