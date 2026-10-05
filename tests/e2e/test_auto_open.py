"""Auto-open after READY (M4 closeout): pages open on the first start, and pages left open from an earlier run
reconnect instead of getting duplicate tabs. Real app subprocesses + real Edge (Playwright); the system browser is
replaced by a logging command through the standard BROWSER variable, so no real tabs are opened.

Run: .venv/Scripts/python -m pytest -m browser tests/e2e/test_auto_open.py -s
"""
import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "lectures" / "photosynthesis.txt"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_app(port: int, log: Path, extra=()) -> subprocess.Popen:
    script = log.with_name("opener.py")  # BROWSER is split with shlex: forward slashes, quoted paths
    script.write_text(f"import sys\nopen({log.as_posix()!r}, 'a').write(sys.argv[1] + chr(10))\n", encoding="utf-8")
    opener = f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}" %s'
    env = {**os.environ, "BROWSER": opener, "COPILOT__DISPLAY__PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    return subprocess.Popen([sys.executable, "-m", "copilot", "--simulate", str(FIXTURE), "--no-wait",
                             "--no-understanding", "--log-level", "WARNING", *extra],
                            # stdin is not a pipe: on Windows a child process (the BROWSER opener) started while another
                            # thread blocks reading a piped stdin hangs; a real console start has no pipe
                            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def wait_up(port: int) -> None:
    for _ in range(150):
        try:
            httpx.get(f"http://127.0.0.1:{port}/api/state", timeout=0.5)
            return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise AssertionError("app did not start")


def stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def opened(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").split() if log.exists() else []


async def test_opens_once_and_reconnecting_tabs_prevent_duplicates(tmp_path):
    from playwright.async_api import async_playwright

    port, log = free_port(), tmp_path / "opened.txt"
    # run 1: nothing connected -> both pages are opened ~3 s after READY
    proc = start_app(port, log)
    try:
        wait_up(port)
        await asyncio.sleep(6)
        assert sorted(opened(log)) == [f"http://localhost:{port}/control", f"http://localhost:{port}/display"]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True)
            pages = [await browser.new_page() for _ in range(2)]
            errors: list[str] = []
            for page in pages:
                page.on("pageerror", lambda e: errors.append(str(e)))
            await pages[0].goto(f"http://127.0.0.1:{port}/control")
            await pages[1].goto(f"http://127.0.0.1:{port}/display")
            await asyncio.sleep(1)
            assert errors == [] and await pages[0].locator(".pill.ok").count() == 1  # control loaded + connected
            stop(proc)
            await asyncio.sleep(4)  # tabs stay open while no server runs (reconnect backoff reaches its 2 s cap)
            # run 2: the old tabs reconnect on their own -> nothing new is opened
            log.unlink()
            proc = start_app(port, log)
            wait_up(port)
            await asyncio.sleep(6)
            assert opened(log) == []
            assert await pages[0].locator(".pill.ok").count() == 1 and errors == []  # the old tab is live again
            await browser.close()
        stop(proc)
        # run 3 with --no-open: nothing opened even with no page connected
        proc = start_app(port, log, ["--no-open"])
        wait_up(port)
        await asyncio.sleep(6)
        assert opened(log) == []
    finally:
        stop(proc)
