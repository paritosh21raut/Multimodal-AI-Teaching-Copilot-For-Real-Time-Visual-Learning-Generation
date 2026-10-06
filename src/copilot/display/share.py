"""Share the live slide with students over the internet: a Cloudflare quick tunnel to this server (F-008).

`share_start` → `cloudflared tunnel --url http://127.0.0.1:<port>` (no account, a random https://….trycloudflare.com
address), its address read from the log, checked until it answers, then `ShareChanged(state=on, url=<address>/view)`.
Students only get the view page; everything else needs the teacher's key from outside (display/server.py).
cloudflared is downloaded once into data/bin when it is not installed. `share_stop` / app end stops the process.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

import httpx

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived, Event, ShareChanged

log = logging.getLogger(__name__)

TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
CHECK_EVERY_S = 1.5
REGISTERED = "Registered tunnel connection"  # cloudflared: the tunnel is connected to Cloudflare's edge
DOH_URL = "https://cloudflare-dns.com/dns-query"
DOH_FALLBACK_WAIT_S = 5.0


def tunnel_url(line: str) -> Optional[str]:
    """The quick tunnel's public address in a cloudflared log line (never Cloudflare's own api / docs addresses)."""
    m = TUNNEL_URL.search(line)
    return m.group(0) if m and not m.group(0).startswith("https://api.") else None


def binary_name() -> str:
    return "cloudflared.exe" if sys.platform == "win32" else "cloudflared"


class ShareService:
    def __init__(self, bus: EventBus, local_url: str, bin_dir: Path, *, configured: str = "", download_url: str = "",
                 start_timeout_s: float = 45.0) -> None:
        self._bus = bus
        self.local_url = local_url
        self.bin_dir = bin_dir
        self.configured = configured
        self.download_url = download_url
        self.start_timeout_s = start_timeout_s
        self.state = "off"
        self.url = ""
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._task: Optional[asyncio.Task] = None

    def attach(self) -> None:
        self._bus.subscribe("share", self._on_command, [CommandReceived])

    async def _on_command(self, event: Event) -> None:
        assert isinstance(event, CommandReceived)
        if event.command.kind == "share_start" and self.state in ("off", "failed"):
            # in the background: starting takes seconds and must not hold up the bus
            self._task = asyncio.create_task(self._start(), name="share:start")
        elif event.command.kind == "share_stop":
            await self.stop()

    async def _publish(self, state: str, url: str = "", detail: str = "") -> None:
        self.state, self.url = state, url
        await self._bus.publish(ShareChanged(state=state, url=url, detail=detail))  # type: ignore[arg-type]

    # ---- cloudflared ---------------------------------------------------------------------------------------
    def find_binary(self) -> Optional[Path]:
        for cand in (self.configured, shutil.which("cloudflared") or "", str(self.bin_dir / binary_name())):
            if cand and Path(cand).is_file():
                return Path(cand)
        return None

    async def _download(self) -> Path:
        if not self.download_url:
            raise RuntimeError("cloudflared is not installed (set [display] cloudflared)")
        target = self.bin_dir / binary_name()
        part = target.with_suffix(".part")
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        log.info("downloading cloudflared from %s", self.download_url)
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30.0, read=60.0)) as client:
            async with client.stream("GET", self.download_url) as r:
                r.raise_for_status()
                with part.open("wb") as f:
                    async for chunk in r.aiter_bytes(1 << 16):
                        f.write(chunk)
        if part.stat().st_size < 5_000_000:  # the real binary is tens of MB; anything small is an error page
            part.unlink()
            raise RuntimeError("cloudflared download was incomplete")
        part.replace(target)
        if sys.platform != "win32":
            target.chmod(0o755)
        return target

    async def _start(self) -> None:
        try:
            await self._publish("starting", detail="starting the link")
            exe = self.find_binary()
            if exe is None:
                await self._publish("starting", detail="downloading cloudflared (once)")
                exe = await self._download()
            self._proc = await asyncio.create_subprocess_exec(
                str(exe), "tunnel", "--no-autoupdate", "--url", self.local_url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            url = await asyncio.wait_for(self._read_url(), self.start_timeout_s)
            await self._publish("starting", detail="waiting for the link to answer")
            await asyncio.wait_for(self._until_registered(), self.start_timeout_s)
            await asyncio.wait_for(self._until_resolvable(url), self.start_timeout_s)
            asyncio.create_task(self._watch(), name="share:watch")
            log.info("sharing %s/view", url)
            await self._publish("on", url=f"{url}/view")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # no network, download blocked, cloudflared error: the teacher sees why
            reason = "the link did not start in time" if isinstance(e, asyncio.TimeoutError) else str(e) or type(e).__name__
            log.warning("sharing failed: %s", reason)
            await self._kill()
            await self._publish("failed", detail=reason)

    async def _read_url(self) -> str:
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            raw = await self._proc.stdout.readline()
            if not raw:
                raise RuntimeError(f"cloudflared exited ({self._proc.returncode})")
            line = raw.decode(errors="replace").rstrip()
            log.debug("cloudflared: %s", line)
            url = tunnel_url(line)
            if url:
                return url

    async def _until_registered(self) -> None:
        """The address is printed before the tunnel is connected to Cloudflare; wait for the connection."""
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            raw = await self._proc.stdout.readline()
            if not raw:
                raise RuntimeError(f"cloudflared exited ({self._proc.returncode})")
            if REGISTERED in raw.decode(errors="replace"):
                return

    async def _until_resolvable(self, url: str) -> None:
        """Announce the link once its name resolves, asked over DNS-over-HTTPS: a lookup through this computer's
        resolver while the brand-new name does not exist yet is cached as "no such name" for minutes, and the link
        then fails here although it works everywhere else (first runtime check, 2026-10-06). Without DoH (blocked
        network) a short wait instead."""
        name = url.removeprefix("https://")
        async with httpx.AsyncClient(timeout=5.0) as client:
            for _ in range(int(self.start_timeout_s / CHECK_EVERY_S)):
                try:
                    r = await client.get(DOH_URL, params={"name": name, "type": "A"},
                                         headers={"accept": "application/dns-json"})
                    if r.status_code == 200 and r.json().get("Answer"):
                        return
                except (httpx.HTTPError, ValueError):
                    await asyncio.sleep(DOH_FALLBACK_WAIT_S)
                    return
                await asyncio.sleep(CHECK_EVERY_S)

    async def _watch(self) -> None:
        """Keep reading the log (a full pipe would stall cloudflared); report a tunnel that closed by itself."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        while await proc.stdout.readline():
            pass
        await proc.wait()
        if self._proc is proc and self.state == "on":
            self._proc = None
            await self._publish("failed", detail="the link closed")

    async def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.returncode is not None:
            return
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        await self._kill()
        if self.state != "off":
            await self._publish("off")
