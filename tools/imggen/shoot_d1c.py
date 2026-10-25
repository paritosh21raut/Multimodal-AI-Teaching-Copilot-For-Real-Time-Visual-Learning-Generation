"""D1c puppet proof contact sheets: artifacts/d1c/index.html frozen at chosen frames -> sheet_{light,dark}.png.

    .venv/Scripts/python tools/imggen/shoot_d1c.py [light|dark|both]
"""
import functools
import http.server
import sys
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "d1c"
CELL = (420, 520)
POSES = [("reference vs puppet (idle)", "idle", 0.0, {"refs": True}, (840, 520)), ("walk", "walk", 0.26, {}, CELL),
         ("run", "run", 0.17, {}, CELL), ("push (effort)", "push", 1.1, {}, (620, 520)),
         ("throw: wind-up", "throw", 0.95, {}, CELL), ("throw: ball flying", "throw", 1.45, {}, (840, 520)),
         ("wave (talking)", "wave", 1.0, {}, CELL), ("point", "point", 1.0, {}, CELL), ("think", "think", 1.0, {}, CELL),
         ("two people", "idle", 1.0, {"B": {"on": True, "clip": "wave", "t": 0.6, "x": 1.1, "dir": -1}}, (620, 520))]
EXPRS = ["neutral", "happy", "thinking", "surprised", "effort", "sad", "angry", "scared"]


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def label(img, text, dark):
    ImageDraw.Draw(img).text((8, 6), text, fill=(226, 232, 240) if dark else (74, 74, 74), font=ImageFont.truetype("segoeui.ttf", 15))
    return img


def sheet(page, theme):
    dark = theme == "dark"
    base = {"theme": theme, "travel": False, "arrows": True, "refs": False, "T": 20.0, "B": {"on": False}}
    row1, row2 = [], []
    for i, (n, clip, t, extra, size) in enumerate(POSES):
        page.set_viewport_size({"width": size[0], "height": size[1]})
        page.evaluate("o => window.pup.set(o)", {**base, **extra, "A": {"clip": clip, "t": t, "expr": "auto", "talk": "auto"}})
        im = Image.open(BytesIO(page.locator("#c").screenshot())).convert("RGB")
        (row1 if i < 5 else row2).append(label(im.resize(size), n, dark))
    faces = []
    page.set_viewport_size({"width": 420, "height": 520})
    for e in EXPRS:
        page.evaluate("o => window.pup.set(o)", {**base, "A": {"clip": "idle", "t": 0, "expr": e, "talk": "off"}})
        x, y, w, h = page.evaluate("() => window.pup.headBox()")
        im = Image.open(BytesIO(page.locator("#c").screenshot(scale="device"))).convert("RGB")
        faces.append(label(im.crop((int(x), int(y), int(x + w), int(y + h))).resize((260, 260)), e, dark))
    rows = [row1, row2, faces]
    W = max(sum(i.width for i in r) for r in rows)
    out = Image.new("RGB", (W, sum(max(i.height for i in r) for r in rows)), (30, 41, 59) if dark else (255, 255, 255))
    y = 0
    for r in rows:
        x = 0
        for i in r:
            out.paste(i, (x, y))
            x += i.width
        y += max(i.height for i in r)
    out.save(OUT / f"sheet_{theme}.png")
    print("wrote", OUT / f"sheet_{theme}.png")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    srv = serve()
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        page = b.new_page(viewport={"width": 420, "height": 520}, device_scale_factor=2)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        try:
            page.goto(f"http://127.0.0.1:{srv.server_address[1]}/artifacts/d1c/index.html?ui=0")
            page.wait_for_function("() => window.pup")
            for theme in (("light", "dark") if which == "both" else (which,)):
                sheet(page, theme)
            page.set_viewport_size({"width": 1600, "height": 900})
            page.evaluate("() => { window.pup.set({theme:'light', travel:true, A:{clip:'run', t:0}, B:{on:true, clip:'walk', t:0, x:1.5, dir:-1}}); window.pup.S.paused = false; }")
            page.wait_for_timeout(4000)
            print("frame ms (2 people, 1600x900 @2x):", round(page.evaluate("() => window.pup.perf()"), 2))
        finally:
            print("errors:", errors[:5])
            b.close()
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    main()
