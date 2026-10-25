"""Stage contact sheets (E1 gate): patches at key frames, the cast in six poses, all props, the backdrops.

    .venv/Scripts/python tools/stage/shoot.py all                 # the four sheets in artifacts/stage/
    .venv/Scripts/python tools/stage/shoot.py patches [name ...]  # tests/fixtures/stage/patches at their keyframes
    .venv/Scripts/python tools/stage/shoot.py cast | props | backdrops
    .venv/Scripts/python tools/stage/shoot.py <patch.json> [...]  # any patch files, at their keyframes (or t = 0)

Serves the repo root on a free port and drives web/stage/dev.html in Edge (Playwright).
"""
import functools
import http.server
import json
import sys
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "stage"
PATCHES = ROOT / "tests" / "fixtures" / "stage" / "patches"
ORDER = ["push", "throw", "carry", "tug", "seesaw", "swing", "rain", "moonmars"]
BACKDROPS = [("outdoor", {}), ("outdoor", {"sky": "overcast"}), ("park", {}), ("street", {}), ("classroom", {}), ("lab_bench", {}),
             ("room", {}), ("night", {}), ("space", {}), ("space", {"ground": "moon"}), ("space", {"ground": "mars"}), ("pool", {}), ("soil", {})]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def sheet(cells, title, out, cols, cell=(800, 500)):
    """cells: [(label, png bytes)] -> one PNG"""
    fb, fs = ImageFont.truetype("segoeuib.ttf", 22), ImageFont.truetype("segoeui.ttf", 18)
    rows = (len(cells) + cols - 1) // cols
    img = Image.new("RGB", (cell[0] * cols + 10 * (cols + 1), 50 + (cell[1] + 34) * rows), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((12, 12), title, fill=(40, 40, 40), font=fb)
    for i, (label, png) in enumerate(cells):
        x, y = 10 + (i % cols) * (cell[0] + 10), 50 + (i // cols) * (cell[1] + 34)
        im = Image.open(BytesIO(png)).convert("RGB").resize(cell, Image.LANCZOS)
        img.paste(im, (x, y))
        d.text((x + 4, y + cell[1] + 6), label, fill=(60, 60, 60), font=fs)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print("wrote", out.relative_to(ROOT))


class Shooter:
    def __init__(self, page):
        self.page = page

    def shot(self, js, arg=None):
        self.page.evaluate(js, arg)
        return self.page.screenshot(type="png")

    def patch(self, p, t):
        return self.shot("([p, t]) => stageDev.show(p, t)", [p, t])


def run(jobs):
    srv = serve()
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        page = b.new_page(viewport={"width": 1600, "height": 1000})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and "favicon" not in m.text and "404" not in m.text and errors.append(m.text))
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/web/stage/dev.html")
        page.wait_for_function("document.title==='ready'", timeout=60000)
        s = Shooter(page)
        for job in jobs:
            job(s)
        b.close()
    srv.shutdown()
    if errors:
        print("console errors:", *errors[:10], sep="\n  ")
        sys.exit(1)


def patches_job(files, out, title):
    def job(s):
        cells = []
        for f in files:
            p = json.loads(Path(f).read_text(encoding="utf-8"))
            for t in p.get("keyframes") or [0]:
                cells.append((f"{p.get('name', Path(f).stem)}  t = {t:.2f} s", s.patch(p, t)))
        sheet(cells, title, out, 3, (640, 400))
    return job


def cast_job(s):
    ids = s.page.evaluate("stageDev.info().cast")
    cells = [(i, s.shot("id => stageDev.show(stageDev.lineup(id), 0)", i)) for i in ids]
    sheet(cells, "Cast: 12 people x 6 poses (walk, push, throw, carry, sit, jump)", OUT / "sheet_cast.png", 2, (960, 600))


def props_job(s):
    rows = s.page.evaluate("stageDev.propGroups(8)")
    cells = []
    for i, ids in enumerate(rows):
        cells.append((", ".join(ids), s.shot("ids => stageDev.show(stageDev.propRow(ids), 1.0)", ids)))
    sheet(cells, "Props at true relative size (each row on its own scale; the bar shows it). Sky things: the size they look.",
          OUT / "sheet_props.png", 2, (960, 600))


def backdrops_job(s):
    cells = [(f"{i} {st or ''}", s.shot("([i, st]) => stageDev.show(stageDev.backdropPanel(i, st), 0)", [i, st])) for i, st in BACKDROPS]
    sheet(cells, "Backdrops (10 + variants), a 1.78 m man for scale", OUT / "sheet_backdrops.png", 3, (640, 400))


def main(argv):
    what = argv[0] if argv else "all"
    fixtures = [PATCHES / f"{n}.json" for n in ORDER]
    if what == "patches":
        names = argv[1:] or ORDER
        jobs = [patches_job([PATCHES / f"{n}.json" for n in names], OUT / "sheet_patches.png", "Reference scenes as stage.patch (hand-made fixtures) at key frames")]
    elif what == "cast":
        jobs = [cast_job]
    elif what == "props":
        jobs = [props_job]
    elif what == "backdrops":
        jobs = [backdrops_job]
    elif what == "all":
        jobs = [cast_job, props_job, backdrops_job, patches_job(fixtures, OUT / "sheet_patches.png", "Reference scenes as stage.patch (hand-made fixtures) at key frames")]
    else:
        jobs = [patches_job(argv, OUT / "sheet_files.png", "Patches")]
    run(jobs)


if __name__ == "__main__":
    main(sys.argv[1:])
