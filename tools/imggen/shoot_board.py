"""D1 style board contact sheets: index.html frozen at t (run mid-stride, lightning on the rod), one PNG per theme.

    .venv/Scripts/python tools/imggen/shoot_board.py [t]  -> artifacts/style_board/sheet_{light,dark}.png
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "artifacts" / "style_board"
t = sys.argv[1] if len(sys.argv) > 1 else "3.1"
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_page(viewport={"width": 1500, "height": 900}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # missing generated pictures are expected (column filled later); only script errors count
    page.on("console", lambda m: m.type == "error" and "ERR_FILE_NOT_FOUND" not in m.text and errors.append(m.text))
    for theme in ("light", "dark"):
        page.goto((OUT / "index.html").as_uri() + f"?theme={theme}&t={t}")
        page.wait_for_timeout(600)
        page.locator("header").evaluate("e => e.style.position = 'static'")
        page.screenshot(path=str(OUT / f"sheet_{theme}.png"), full_page=True)
    print("errors:", errors[:5])
    b.close()
