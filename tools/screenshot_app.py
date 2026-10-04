"""Run the real app (subprocess) and screenshot /control and /display mid-lecture.

    .venv/Scripts/python tools/screenshot_app.py [extra copilot args...]
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "app"
PORT = 8765


async def main(extra: list[str]) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-m", "copilot", "--no-wait", "--log-level", "WARNING"] + (extra or [
        "--simulate", "tests/fixtures/lectures/photosynthesis.txt", "--demo-slides", "--speed", "3"])
    proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            try:
                httpx.get(f"http://127.0.0.1:{PORT}/api/state", timeout=0.5)
                break
            except httpx.HTTPError:
                time.sleep(0.2)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True)
            control = await browser.new_page(viewport={"width": 1440, "height": 900})
            display = await browser.new_page(viewport={"width": 1280, "height": 720})
            errors: list[str] = []
            for page in (control, display):
                page.on("pageerror", lambda e: errors.append(str(e)))
            await control.goto(f"http://127.0.0.1:{PORT}/control")
            await display.goto(f"http://127.0.0.1:{PORT}/display")
            await asyncio.sleep(14)
            await control.screenshot(path=str(OUT / "control.png"))
            await display.screenshot(path=str(OUT / "display.png"))
            await control.keyboard.press("b")  # teacher blanks the projector from the control view
            await asyncio.sleep(1)
            await display.screenshot(path=str(OUT / "display_blank.png"))
            await control.screenshot(path=str(OUT / "control_blank.png"))
            await browser.close()
            print("page errors:", errors)
    finally:
        proc.stdin.write("q\n")
        proc.stdin.flush()
        try:
            out, _ = proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        print(out[-1500:])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
