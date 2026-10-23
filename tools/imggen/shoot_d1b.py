"""D1b look test contact sheets: artifacts/d1b/index.html frozen at chosen frames -> sheet_{light,dark}.png.

    .venv/Scripts/python tools/imggen/shoot_d1b.py [light|dark|both] [--perf]
--perf: also run the page live for 8 s and print fps / frame ms / draw calls / GPU (+ nvidia-smi VRAM).
"""
import functools
import http.server
import subprocess
import sys
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "d1b"
REF = ROOT / "whatsapp_artifacts"
CELL = (300, 400)
FACE = (300, 300)

VIEWS = [("front", "front"), ("3/4 front", "q34"), ("side", "side"), ("3/4 back", "back34"), ("back", "back"), ("top", "top")]
EXPRS = ["neutral", "happy", "thinking", "surprised", "effort", "sad", "angry", "scared"]
POSES = [  # label, A clip, clip time, camera, extra
    ("walk", "walk", 0.26, "side", {}), ("run", "run", 0.17, "side", {}), ("push", "push", 1.1, "side", {}),
    ("throw: wind-up", "throw", 0.95, "q34", {}), ("throw: ball flying", "throw", 1.75, "side", {}),
    ("wave (talking)", "wave", 1.0, "front", {}), ("point", "point", 1.0, "front", {}), ("think", "think", 1.0, "q34", {}),
    ("walk, top view", "walk", 0.5, "top", {}), ("push, high angle", "push", 1.4, "high", {}),
    ("two men", "idle", 1.0, "q34", {"B": {"on": True, "clip": "wave", "t": 0.6}}),
    ("run, low angle", "run", 0.5, "low", {}),
]


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def shot(page, size, opts):
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.evaluate("o => window.d1b.set(o)", opts)
    return Image.open(BytesIO(page.locator("#c").screenshot())).convert("RGB")


def label(img, text, dark):
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("segoeui.ttf", 15)
    d.text((8, 6), text, fill=(226, 232, 240) if dark else (74, 74, 74), font=f)
    return img


def sheet(page, theme):
    dark = theme == "dark"
    bg = (30, 41, 59) if dark else (255, 255, 255)
    base = {"theme": theme, "travel": False, "arrows": True, "T": 20.0, "B": {"on": False}}
    rows = []
    # row 1: turnaround (idle, neutral)
    rows.append([label(shot(page, CELL, {**base, "cam": c, "A": {"clip": "idle", "t": 0.0, "expr": "neutral", "talk": "off"}}), n, dark)
                 for n, c in VIEWS])
    # row 2: expressions front, row 3: three of them in 3/4 and profile
    rows.append([label(shot(page, FACE, {**base, "cam": "face", "A": {"clip": "idle", "t": 0.0, "expr": e, "talk": "off"}}), e, dark)
                 for e in EXPRS])
    rows.append([label(shot(page, FACE, {**base, "cam": c, "A": {"clip": "idle", "t": 0.0, "expr": e, "talk": "off"}}), f"{e} {n}", dark)
                 for e in ("neutral", "happy", "effort", "surprised") for n, c in (("3/4", "face34"), ("profile", "faceSide"))])
    # rows 4-5: poses
    cells = []
    for n, clip, t, cam, extra in POSES:
        o = {**base, "cam": cam, "A": {"clip": clip, "t": t, "expr": "auto", "talk": "auto"}, **extra}
        cells.append(label(shot(page, CELL, o), n, dark))
    rows += [cells[:6], cells[6:]]
    # reference strip
    ref = Image.open(REF / "man in all poses.jpg").convert("RGB")
    W = max(sum(i.width for i in r) for r in rows)
    ref = ref.resize((W, int(ref.height * W / ref.width)))
    H = ref.height + sum(max(i.height for i in r) for r in rows)
    out = Image.new("RGB", (W, H), bg)
    out.paste(ref, (0, 0))
    y = ref.height
    for r in rows:
        x = 0
        for i in r:
            out.paste(i, (x, y))
            x += i.width
        y += max(i.height for i in r)
    out.save(OUT / f"sheet_{theme}.png")
    print("wrote", OUT / f"sheet_{theme}.png")


def perf(page):
    page.set_viewport_size({"width": 1600, "height": 900})
    page.evaluate("() => window.d1b.set({theme:'light', travel:true, arrows:true, cam:'q34', A:{clip:'run', t:0}, B:{on:true, clip:'walk', t:0}})")
    page.evaluate("() => { window.d1b.S.paused = false; }")
    page.wait_for_timeout(8000)
    try:
        vram = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        vram = "nvidia-smi not found"
    print("perf:", page.evaluate("() => window.d1b.info()"), "| nvidia-smi:", vram)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "both"
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/artifacts/d1b/index.html?ui=0"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True,
                              args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11", "--force_high_performance_gpu"])
        page = b.new_page(viewport={"width": 300, "height": 400}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        try:
            page.goto(url)
            page.wait_for_function("() => window.d1b")
            for theme in (("light", "dark") if which == "both" else (which,)):
                sheet(page, theme)
            if "--perf" in sys.argv:
                perf(page)
        finally:
            print("errors:", errors[:5])
            b.close()
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    main()
