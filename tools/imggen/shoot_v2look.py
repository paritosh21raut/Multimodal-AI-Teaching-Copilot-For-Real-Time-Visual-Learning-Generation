"""V2 look samples contact sheet: artifacts/v2look/index.html -> artifacts/v2look/sheet_light.png.

    .venv/Scripts/python tools/imggen/shoot_v2look.py [row ...]
Rows are candidate+shade keys (default: A-toon A-flat B-toon C-toon); columns are the four scenes.
Assets are CC0 packs under artifacts/v2look/assets (git-ignored; see docs/v2/V2-PLAN.md for sources).
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
OUT = ROOT / "artifacts" / "v2look"
CELL = (560, 380)
SCENES = ["push", "throw", "street", "face"]
ROWS = {
    "A-toon": "A  mannequin + painted clothes + drawn face  (toon)",
    "A-flat": "A  mannequin + painted clothes + drawn face  (flat)",
    "B-toon": "B  base body + painted clothes + own face  (toon)",
    "B-flat": "B  base body + painted clothes + own face  (flat)",
    "C-toon": "C  Kenney mini characters  (toon)",
    "C-flat": "C  Kenney mini characters  (flat)",
}


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(rows):
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/artifacts/v2look/index.html"
    f = ImageFont.truetype("segoeui.ttf", 18)
    fb = ImageFont.truetype("segoeuib.ttf", 20)
    head, side = 34, 0
    sheet = Image.new("RGB", (CELL[0] * len(SCENES), head + (CELL[1] + 30) * len(rows)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, s in enumerate(SCENES):
        d.text((i * CELL[0] + 10, 6), s, fill=(60, 60, 60), font=fb)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True,
                              args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"])
        page = b.new_page(viewport={"width": CELL[0], "height": CELL[1]}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(url)
        page.wait_for_function("document.title==='done'||document.title==='error'", timeout=180000)
        for r, key in enumerate(rows):
            cand, shade = key.split("-")
            y = head + r * (CELL[1] + 30)
            d.text((10, y + 4), ROWS[key], fill=(40, 40, 40), font=f)
            for c, scene in enumerate(SCENES):
                page.evaluate("o => window.look.set(o)", {"cand": cand, "shade": shade, "scene": scene,
                                                          "w": CELL[0], "h": CELL[1]})
                img = Image.open(BytesIO(page.locator("#c").screenshot())).convert("RGB")
                sheet.paste(img, (c * CELL[0] + side, y + 30))
        b.close()
    out = OUT / "sheet_light.png"
    sheet.save(out)
    print("wrote", out, sheet.size)
    for e in errors[:10]:
        print("error:", e)



def more(cand="B", shade="toon"):
    """All scenes of one candidate in a 2-column grid -> artifacts/v2look/sheet_<cand>_<shade>_more.png."""
    scenes = ["push", "throw", "carry", "rain", "jump", "beaker", "table", "street", "class", "face"]
    cell, cols = (800, 500), 2
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/artifacts/v2look/index.html?cand={cand}&shade={shade}"
    fb = ImageFont.truetype("segoeuib.ttf", 22)
    rows = (len(scenes) + cols - 1) // cols
    sheet = Image.new("RGB", (cell[0] * cols + 10 * (cols + 1), 50 + (cell[1] + 10) * rows), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((12, 12), f"3D samples  ·  {ROWS[cand + '-' + shade]}  ·  clothes smoothed, 4 cast looks", fill=(40, 40, 40), font=fb)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True,
                              args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"])
        page = b.new_page(viewport={"width": cell[0], "height": cell[1]}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and "404" not in m.text and errors.append(m.text))
        page.goto(url)
        page.wait_for_function("document.title==='done'||document.title==='error'", timeout=180000)
        for i, scene in enumerate(scenes):
            try:
                page.evaluate("o => window.look.set(o)", {"cand": cand, "shade": shade, "scene": scene, "w": cell[0], "h": cell[1]})
            except Exception as e:  # noqa: BLE001 - report and keep the sheet going
                errors.append(f"{scene}: {e}")
                continue
            img = Image.open(BytesIO(page.locator("#c").screenshot())).convert("RGB")
            sheet.paste(img, (10 + (i % cols) * (cell[0] + 10), 50 + (i // cols) * (cell[1] + 10)))
        b.close()
    out = OUT / f"sheet_{cand}_{shade}_more.png"
    sheet.save(out)
    print("wrote", out, sheet.size)
    for e in errors[:10]:
        print("error:", e)


if __name__ == "__main__":
    if sys.argv[1:2] == ["more"]:
        more(*sys.argv[2:4])
    else:
        main(sys.argv[1:] or ["A-toon", "A-flat", "B-toon", "C-toon"])
