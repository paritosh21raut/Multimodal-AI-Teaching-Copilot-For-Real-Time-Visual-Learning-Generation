"""Any notes file → PDF (F-010b §5), so every kind uses the one PDF pipeline (pages, rendering, following the lecture).

    PDF                         as it is
    Word  .docx .doc .rtf .odt  Microsoft Word (COM, hidden, read-only) → PDF
    Slides .pptx .ppt .odp      Microsoft PowerPoint (COM) → PDF
    Text  .txt .md              a plain page printed by headless Edge
    Image .png .jpg .webp .gif  a one-page PDF (Pillow)
    Link  http(s)://…           the page opened in headless Edge and printed (a snapshot: layout, images, text)

Office missing or failing → `BadNotes` with the reason for the teacher (nothing is made up).
"""
from __future__ import annotations

import asyncio
import html
import io
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from copilot.notes.library import BadNotes

log = logging.getLogger(__name__)

WORD = {".docx", ".doc", ".rtf", ".odt"}
SLIDES = {".pptx", ".ppt", ".odp"}
TEXT = {".txt", ".md", ".markdown"}
IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ACCEPT = sorted({".pdf"} | WORD | SLIDES | TEXT | IMAGE)
OFFICE_TIMEOUT_S = 120
WEB_TIMEOUT_MS = 30_000
TEXT_MAX_CHARS = 400_000
OFFICE_SCRIPT = Path(__file__).with_name("office_to_pdf.ps1")


def kind_of(name: str) -> Optional[str]:
    ext = Path(name.lower()).suffix
    if ext == ".pdf":
        return "pdf"
    for kind, exts in (("word", WORD), ("slides", SLIDES), ("text", TEXT), ("image", IMAGE)):
        if ext in exts:
            return kind
    return None


async def to_pdf(data: bytes, name: str) -> tuple[bytes, str]:
    """(PDF bytes, kind) for a file the teacher added."""
    kind = kind_of(name)
    if kind is None:
        raise BadNotes("use a PDF, Word, PowerPoint, text or image file")
    if kind == "pdf":
        return data, kind
    if kind == "image":
        return await asyncio.to_thread(image_pdf, data), kind
    if kind == "text":
        return await html_pdf(text_page(Path(name).stem, data.decode("utf-8", errors="replace"),
                                        markdown=Path(name).suffix.lower() != ".txt")), kind
    return await asyncio.to_thread(office_pdf, data, name, kind), kind


def image_pdf(data: bytes) -> bytes:
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise BadNotes(f"the image could not be opened ({e})") from e
    if img.mode not in ("RGB", "L"):
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
        img = bg
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=150.0)
    return out.getvalue()


def office_pdf(data: bytes, name: str, kind: str) -> bytes:
    app = "word" if kind == "word" else "powerpoint"
    with tempfile.TemporaryDirectory(prefix="copilot-notes-") as tmp:
        src = Path(tmp) / f"in{Path(name).suffix.lower()}"
        out = Path(tmp) / "out.pdf"
        src.write_bytes(data)
        try:
            run = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                 str(OFFICE_SCRIPT), "-App", app, "-In", str(src), "-Out", str(out)],
                capture_output=True, text=True, timeout=OFFICE_TIMEOUT_S)
        except FileNotFoundError as e:
            raise BadNotes("Word and PowerPoint files need Windows PowerShell and Microsoft Office") from e
        except subprocess.TimeoutExpired as e:
            raise BadNotes(f"{app.title()} did not finish the conversion in {OFFICE_TIMEOUT_S} s") from e
        if run.returncode != 0 or not out.is_file():
            detail = (run.stderr or run.stdout or "").strip().splitlines()
            reason = detail[-1] if detail else f"exit code {run.returncode}"
            log.warning("office conversion of %r failed: %s", name, (run.stderr or run.stdout)[-800:])
            if "80040154" in reason or "class not registered" in reason.lower():
                raise BadNotes(f"this file needs Microsoft {'Word' if app == 'word' else 'PowerPoint'} on this laptop")
            raise BadNotes(f"{'Word' if app == 'word' else 'PowerPoint'} could not convert it ({reason[:160]})")
        return out.read_bytes()


def text_page(title: str, text: str, markdown: bool) -> str:
    """A readable page for a .txt / .md file: paragraphs kept, Markdown headings and bullets shown as such."""
    text = text[:TEXT_MAX_CHARS]
    body: list[str] = []
    for line in text.splitlines():
        h = re.match(r"(#{1,4})\s+(.*)", line) if markdown else None
        if h:
            body.append(f"<h{len(h.group(1)) + 1}>{html.escape(h.group(2))}</h{len(h.group(1)) + 1}>")
        elif markdown and re.match(r"\s*[-*+]\s+", line):
            item = html.escape(re.sub(r"^\s*[-*+]\s+", "", line))
            body.append(f'<p class="li">• {item}</p>')
        elif line.strip():
            body.append(f"<p>{html.escape(line)}</p>")
        else:
            body.append('<div class="gap"></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
@page {{ size: A4; margin: 18mm 18mm 20mm; }}
body {{ font: 11.5pt/1.55 "Segoe UI", system-ui, sans-serif; color: #1c2128; }}
h1 {{ font-size: 17pt; margin: 0 0 6mm; }} h2 {{ font-size: 15pt; margin: 5mm 0 2mm; }}
h3 {{ font-size: 13pt; margin: 4mm 0 2mm; }} h4, h5 {{ font-size: 11.5pt; margin: 3mm 0 1mm; }}
p {{ margin: 0; white-space: pre-wrap; }} p.li {{ padding-left: 5mm; }} .gap {{ height: 3mm; }}
</style></head><body><h1>{html.escape(title)}</h1>{"".join(body)}</body></html>"""


async def _edge():
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(channel="msedge", headless=True)
    except Exception:
        await pw.stop()
        raise
    return pw, browser


async def html_pdf(page_html: str) -> bytes:
    pw, browser = await _edge()
    try:
        page = await browser.new_page()
        await page.set_content(page_html, wait_until="load")
        return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
    finally:
        await browser.close()
        await pw.stop()


def clean_url(url: str) -> str:
    url = (url or "").strip()
    if not re.match(r"https?://[^\s/$.?#][^\s]*$", url, re.I):
        raise BadNotes("drop a web link (http:// or https://)")
    return url[:2000]


async def web_pdf(url: str) -> tuple[bytes, str]:
    """(PDF snapshot, page title) of a web page, as the teacher would see it printed."""
    url = clean_url(url)
    pw, browser = await _edge()
    try:
        page = await browser.new_page(viewport={"width": 1200, "height": 900})
        try:
            response = await page.goto(url, wait_until="load", timeout=WEB_TIMEOUT_MS)
        except Exception as e:  # DNS, offline, timeout
            raise BadNotes(f"the page could not be opened ({str(e).splitlines()[0][:160]})") from e
        if response is not None and response.status >= 400:
            raise BadNotes(f"the site answered {response.status}: the page could not be saved")
        try:  # late images / lazy content
            await page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        title = " ".join((await page.title() or "").split())[:120]
        await page.emulate_media(media="screen")  # the page as seen, not its print style (often bare text)
        pdf = await page.pdf(format="A4", print_background=True, margin={"top": "10mm", "bottom": "10mm",
                                                                         "left": "8mm", "right": "8mm"})
        return pdf, title
    finally:
        await browser.close()
        await pw.stop()
