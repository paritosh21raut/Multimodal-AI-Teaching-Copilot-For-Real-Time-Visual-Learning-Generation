"""V2 2D look samples contact sheets from artifacts/v2look/2d.html.

    .venv/Scripts/python tools/imggen/shoot_v2look2d.py <out-name> <theme> <fig[,fig...]> [scene ...]
One figure style -> its scenes in a 2-column grid; several styles -> each scene once per style.
Examples:
    ... sheet2d_explainer_shaped_a explainer shaped push throw carry rain moonmars beaker table street
    ... sheet2d_cast_styles explainer flat,shaped,chibi,toon3d cast
Needs artifacts/v2look/motion.json (tools/imggen/bake_motion.py).
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
CELL = (800, 500)
COLS = 2


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(name, theme, figs, scenes):
    figs = figs.split(",")
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/artifacts/v2look/2d.html?shoot=1"
    fb = ImageFont.truetype("segoeuib.ttf", 22)
    fs = ImageFont.truetype("segoeui.ttf", 18)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True, args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"])
        page = b.new_page(viewport={"width": CELL[0], "height": CELL[1]}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and "404" not in m.text and "texture" not in m.text and errors.append(m.text))
        page.goto(url)
        page.wait_for_function("document.title==='done'", timeout=60000)
        scenes = scenes or page.evaluate("window.v2.ORDER")
        cells = [(s, f) for s in scenes for f in figs]
        for f in figs:
            page.evaluate("f => window.v2.ready(f)", f)
        rows = (len(cells) + COLS - 1) // COLS
        sheet = Image.new("RGB", (CELL[0] * COLS + 10 * (COLS + 1), 50 + (CELL[1] + 34) * rows), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        d.text((12, 12), f"2D samples  ·  theme: {theme}  ·  people: {', '.join(figs)}", fill=(40, 40, 40), font=fb)
        for i, (scene, fig) in enumerate(cells):
            x, y = 10 + (i % COLS) * (CELL[0] + 10), 50 + (i // COLS) * (CELL[1] + 34)
            try:
                page.evaluate("""([n, th, f]) => { const r = document.getElementById('root');
                    r.innerHTML = window.v2.svgOf(n, th, f, window.v2.still(n));
                    const s = r.firstChild; s.setAttribute('width', 800); s.setAttribute('height', 500); }""", [scene, theme, fig])
                img = Image.open(BytesIO(page.locator("#root svg").screenshot())).convert("RGB")
                sheet.paste(img, (x, y + 24))
            except Exception as e:  # noqa: BLE001 - keep the sheet going, report at the end
                errors.append(f"{scene}/{fig}: {str(e)[:200]}")
            d.text((x + 2, y), f"{scene}  ·  {fig}", fill=(90, 90, 90), font=fs)
        b.close()
    out = OUT / f"{name}.png"
    sheet.save(out)
    print("wrote", out, sheet.size)
    for e in errors[:12]:
        print("error:", e)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
