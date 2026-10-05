"""Run the real app (subprocess) and screenshot /control and /display mid-lecture.

    .venv/Scripts/python tools/screenshot_app.py [extra copilot args...]
    .venv/Scripts/python tools/screenshot_app.py --lecture [extra copilot args...]

--lecture: capture the whole lecture (display + control whenever the live slide changes) into
artifacts/app/lecture_<fixture>/, plus the control view whenever a new concern card appears. Nothing is clicked,
so the screenshots show the default (truthful-slide) behaviour.
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


async def lecture(control, display, proc, errors: list[str], name: str = "lecture") -> None:
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    n, last, concerns, t0 = 0, None, 0, time.time()
    while proc.poll() is None:
        await asyncio.sleep(1.0)
        try:
            state = httpx.get(f"http://127.0.0.1:{PORT}/api/state", timeout=1).json()
        except httpx.HTTPError:
            break
        deck = state.get("deck") or {}
        live = deck.get("live_id")
        spec = (state.get("slides") or {}).get(live) or {}
        key = (live, spec.get("version"))
        if key != last and live:
            last, n = key, n + 1
            await asyncio.sleep(0.6)  # let the transition settle
            tag = f"{n:02d}_{int(time.time() - t0):03d}s"
            await display.screenshot(path=str(out / f"display_{tag}.png"))
            await control.screenshot(path=str(out / f"control_{tag}.png"))
            print(f"[shot] {tag} {spec.get('title')!r} v{spec.get('version')}", flush=True)
        count = await control.locator(".concern").count()
        if count > concerns:
            concerns = count
            await control.screenshot(path=str(out / f"control_concern_{count}.png"))
            print(f"[shot] concern card #{count}", flush=True)


async def main(extra: list[str]) -> None:
    whole = bool(extra) and extra[0] == "--lecture"
    name = "lecture"
    if whole:
        extra = extra[1:] or ["--simulate", "tests/fixtures/lectures/photosynthesis.txt", "--speed", "1"]
        if "--simulate" in extra:
            name = "lecture_" + Path(extra[extra.index("--simulate") + 1]).stem
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-m", "copilot", "--no-wait", "--log-level", "WARNING"] + (extra or [
        "--simulate", "tests/fixtures/lectures/photosynthesis.txt", "--demo-slides", "--speed", "3"])
    log_path = OUT / "app_output.txt"  # a file, not a pipe: a long run must never block on a full pipe buffer
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT, text=True,
                            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
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
            if whole:
                await lecture(control, display, proc, errors, name)
                await browser.close()
                print("page errors:", errors)
                return
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
        try:
            proc.stdin.write("q\n")
            proc.stdin.flush()
        except OSError:
            pass  # already exited
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
        out = log_path.read_text(encoding="utf-8", errors="replace")
        print(out[-6000:] if whole else out[-1500:])


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # app output can contain characters the console codepage lacks
    asyncio.run(main(sys.argv[1:]))
