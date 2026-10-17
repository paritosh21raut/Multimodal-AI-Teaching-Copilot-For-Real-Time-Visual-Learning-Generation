"""Figures from educational web pages (F-013 S4, user 2026-10-17: "extract images, block diagrams or diagrams from
relevant educational websites which give the best results").

    a web search (no key, ~1 s)  ->  the first result pages that are not PDFs, social sites, shops or
    file mirrors (≤ 3, robots.txt respected)  ->  the pictures on those pages whose own words (alt text, figure caption,
    file name, the heading above them) name what was asked  ->  `Candidate`s for the finder, which judges them with
    CLIP like every other image.

Search: DuckDuckGo's HTML page, else Bing's (see `search_pages`). Why pages and not an image search: DuckDuckGo's
image endpoint refuses scripts (HTTP 202), and Bing's image results
for "hypothalamus diagram" / "STM32 block diagram" were aggregator and shop pages; the page results were kenhub,
Cleveland Clinic, wiki.st.com. Commons alone gave a fish forebrain for "forebrain diagram" (test13).
These pictures are not free-licensed: each one keeps its page as the credit (shown with the image in /control, kept
in exports), for showing in the teacher's own classroom.
"""
from __future__ import annotations

import asyncio
import base64
import html as htmlmod
import logging
import re
import time
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from copilot.visuals.sources import Candidate

log = logging.getLogger(__name__)

SEARCH_URL = "https://lite.duckduckgo.com/lite/"
BING_URL = "https://www.bing.com/search"
PAGE_TIMEOUT_S = 4.0
# a browser's name (several educational sites refuse unknown clients) plus ours, for robots.txt rules naming us
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 "
              "Safari/537.36 TeachingCopilot/0.1")
ROBOT_NAME = "TeachingCopilot"
MAX_PAGES = 3
MAX_PAGE_BYTES = 3_000_000
PER_PAGE = 4          # pictures taken from one page
MIN_DECLARED_PX = 250  # an <img> that says it is smaller than this is an icon or a thumbnail
# never a source of classroom figures: social sites, video, shops, file mirrors, paywalled papers, Q&A
_SKIP_HOSTS = re.compile(
    r"(?:^|\.)(?:youtube\.com|youtu\.be|facebook\.com|instagram\.com|twitter\.com|x\.com|tiktok\.com|pinterest\.\w+|"
    r"reddit\.com|quora\.com|linkedin\.com|amazon\.\w+|ebay\.\w+|aliexpress\.com|indiamart\.com|alibaba\.com|"
    r"flipkart\.com|scribd\.com|researchgate\.net|academia\.edu|slideshare\.net|coursehero\.com|chegg\.com|"
    r"studocu\.com|brainly\.\w+|quizlet\.com|shutterstock\.com|alamy\.com|gettyimages\.\w+|istockphoto\.com|"
    r"dreamstime\.com|depositphotos\.com|123rf\.com|vecteezy\.com|freepik\.com|adobe\.com|duckduckgo\.com)$",
    re.IGNORECASE)
_NOT_FIGURE = re.compile(r"logo|icon|avatar|sprite|banner|badge|emoji|spinner|loading|placeholder|pixel|tracking|"
                         r"advert|\bads?\b|social|share|facebook|twitter|whatsapp|author|profile|gravatar|"
                         r"thumb(?:nail)?s?[-_]|button|arrow|flag", re.IGNORECASE)
_IMAGE_EXT = re.compile(r"\.(jpe?g|png|webp)(?:$|\?)", re.IGNORECASE)
_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
# words of the query that say what kind of picture, not what it shows
_KIND_WORDS = {"diagram", "diagrams", "block", "schematic", "schematics", "figure", "picture", "image", "photo",
               "labelled", "labeled", "illustration", "flowchart", "chart", "drawing", "structure", "of", "the", "a",
               "an", "and", "in", "with"}
_FIGURE_TYPES = ("block diagram", "circuit diagram", "schematic", "pinout", "pin diagram", "flowchart", "flow chart",
                 "architecture", "timing diagram", "ray diagram", "free body diagram", "energy level diagram")

_robots: dict[str, tuple[float, Optional[RobotFileParser]]] = {}  # host -> (fetched at, rules or None = no rules)
ROBOTS_TTL_S = 6 * 3600


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w


def subject_words(query: str) -> list[str]:
    """What the picture must show: the query without its picture-kind words ("STM32 block diagram" -> stm32)."""
    return [w for w in _words(query) if w not in _KIND_WORDS and len(w) >= 2]


def figure_type(query: str) -> str:
    """The kind of figure asked for, when the query names one ("STM32 block diagram" -> "block diagram")."""
    q = " ".join(_words(query))
    return next((t for t in _FIGURE_TYPES if t in q), "")


def match_score(context: str, query: str) -> float:
    """How well a picture's own words name the query: the share of subject words found (stem match, also run
    together: "STM32F103" holds "stm32"), and the figure type when one was asked for. 0 when a subject word is missing
    (precision first: a page about the topic has many unrelated pictures)."""
    words = subject_words(query)
    if not words:
        return 0.0
    hay = " ".join(_words(context))
    squashed = hay.replace(" ", "")
    found = sum(1 for w in words if _stem(w) in hay or _stem(w) in squashed)
    if found < len(words):
        return 0.0
    kind = figure_type(query)
    if kind and kind.replace(" ", "") not in squashed and kind.split()[0] not in hay:
        return 0.0
    return 1.0 if kind else 0.8


def _bing_target(href: str) -> str:
    """Bing wraps results in /ck/a?...&u=a1<base64url of the target>."""
    href = htmlmod.unescape(href)
    u = parse_qs(urlparse(href).query).get("u", [""])[0]
    if u.startswith("a1"):
        raw = u[2:] + "=" * (-len(u[2:]) % 4)
        try:
            return base64.urlsafe_b64decode(raw).decode("utf-8", "replace")
        except (ValueError, UnicodeError):
            return ""
    return href


def _ddg_results(text: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*class=['\"]result-link['\"][^>]*>(.*?)</a>", text, re.S):
        url = htmlmod.unescape(m.group(1))
        if "duckduckgo.com/l/" in url:  # a redirect link: the target is its uddg parameter
            url = parse_qs(urlparse(url).query).get("uddg", [url])[0]
        out.append((url, re.sub(r"<[^>]+>", " ", m.group(2))))
    return out


def _bing_results(text: str) -> list[tuple[str, str]]:
    return [(_bing_target(h), re.sub(r"<[^>]+>", " ", t)) for h, t in
            re.findall(r'<li class="b_algo"[^>]*>.*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.S)]


# DuckDuckGo answers a burst of scripted searches with a "select the ducks" page (HTTP 202, after ~6 in a minute):
# then it rests for a while and Bing answers. Bing in turn sometimes returns unrelated pages to scripts ("nephron
# diagram" -> Chrome downloads), so only results whose title or address names the subject are kept.
_rest_until: dict[str, float] = {}
ENGINE_REST_S = 900.0


async def search_pages(c: httpx.AsyncClient, query: str, limit: int = MAX_PAGES) -> list[str]:
    """Result pages for the query (HTML pages naming the subject; skipped hosts left out), best first."""
    words = subject_words(query)
    for engine in ("duckduckgo", "bing"):
        if time.monotonic() < _rest_until.get(engine, 0.0):
            continue
        try:
            if engine == "duckduckgo":
                r = await c.post(SEARCH_URL, data={"q": query}, headers={"User-Agent": BROWSER_UA})
                results = _ddg_results(r.text) if r.status_code == 200 else []
            else:
                r = await c.get(BING_URL, params={"q": query, "setlang": "en", "cc": "US"},
                                headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"})
                results = _bing_results(r.text) if r.status_code == 200 else []
        except httpx.HTTPError as e:
            log.info("web search %s for %r: %s", engine, query, type(e).__name__)
            continue
        if r.status_code != 200 or not results:
            if r.status_code != 200 or engine == "duckduckgo":
                _rest_until[engine] = time.monotonic() + ENGINE_REST_S
                log.info("web search %s refused %r (HTTP %d): resting %.0f min", engine, query, r.status_code,
                         ENGINE_REST_S / 60)
            continue
        out: list[str] = []
        for url, title in results:
            host = urlparse(url).hostname or ""
            hay = " ".join(_words(f"{title} {url}"))
            if (not url.startswith("http") or _SKIP_HOSTS.search(host)
                    or re.search(r"\.(pdf|docx?|pptx?)(?:$|\?)", url, re.I)
                    or not any(_stem(w) in hay or _stem(w) in hay.replace(" ", "") for w in words)):
                continue
            if url not in out:
                out.append(url)
            if len(out) >= limit:
                break
        if out:
            return out
        log.info("web search %s for %r: no result names it", engine, query)
    return []


async def allowed(c: httpx.AsyncClient, url: str) -> bool:
    """robots.txt allows our client to fetch the page (no robots.txt, or an unreachable one, allows it)."""
    p = urlparse(url)
    host = f"{p.scheme}://{p.netloc}"
    now = time.monotonic()
    hit = _robots.get(host)
    if hit is None or now - hit[0] > ROBOTS_TTL_S:
        rules: Optional[RobotFileParser] = None
        try:
            r = await c.get(f"{host}/robots.txt", headers={"User-Agent": BROWSER_UA}, timeout=2.5)
            if r.status_code == 200:
                rules = RobotFileParser()
                rules.parse(r.text.splitlines())
        except httpx.HTTPError:
            rules = None
        _robots[host] = hit = (now, rules)
    rules = hit[1]
    return rules is None or (rules.can_fetch(ROBOT_NAME, url) and rules.can_fetch("*", url))


def _src(img, base: str) -> str:
    """The picture's address: a lazy-loading attribute first, then the largest srcset entry, then src."""
    for attr in ("data-src", "data-lazy-src", "data-original", "data-orig-file", "data-large-file"):
        v = (img.get(attr) or "").strip()
        if v and not v.startswith("data:"):
            return urljoin(base, v)
    srcset = img.get("srcset") or img.get("data-srcset") or ""
    best, best_w = "", 0
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = int(bits[1][:-1]) if len(bits) > 1 and bits[1].endswith("w") and bits[1][:-1].isdigit() else 1
        if w >= best_w:
            best, best_w = bits[0], w
    v = best or (img.get("src") or "").strip()
    return "" if not v or v.startswith("data:") else urljoin(base, v)


def _int(v) -> int:
    try:
        return int(str(v).strip().rstrip("px"))
    except (TypeError, ValueError):
        return 0


def page_figures(page_html: str, page_url: str, query: str, rank: int = 0) -> list[Candidate]:
    """The pictures of one page whose own words name the query, best named first (≤ PER_PAGE)."""
    import lxml.html

    try:
        doc = lxml.html.document_fromstring(page_html)
    except (ValueError, lxml.etree.ParserError):
        return []
    host = (urlparse(page_url).hostname or "").removeprefix("www.")
    title = " ".join((doc.findtext(".//title") or "").split())
    found: list[tuple[float, int, Candidate]] = []
    seen: set[str] = set()
    for i, img in enumerate(doc.iter("img")):
        src = _src(img, page_url)
        if not src or src in seen or not _IMAGE_EXT.search(src):
            continue
        seen.add(src)
        alt = " ".join((img.get("alt") or img.get("title") or "").split())
        name = re.sub(r"[-_.]+", " ", urlparse(src).path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        if _NOT_FIGURE.search(f"{src} {img.get('class') or ''} {alt}"):
            continue
        w, h = _int(img.get("width")), _int(img.get("height"))
        if (w and w < MIN_DECLARED_PX) or (h and h < MIN_DECLARED_PX * 0.6):
            continue
        fig = next((a for a in img.iterancestors() if a.tag == "figure"), None)
        caption = " ".join(fig.findtext(".//figcaption", "").split()) if fig is not None else ""
        if not caption and fig is not None:
            cap = fig.find(".//figcaption")
            caption = " ".join(cap.text_content().split()) if cap is not None else ""
        heading_el = img.xpath("preceding::*[self::h1 or self::h2 or self::h3 or self::h4][1]")
        heading = " ".join(heading_el[0].text_content().split())[:120] if heading_el else ""
        own = f"{alt} {caption} {name}"
        # the picture's own words first; the heading above it counts only together with them
        score = max(match_score(own, query), 0.9 * match_score(f"{own} {heading}", query))
        if score <= 0:
            continue
        ext = _IMAGE_EXT.search(src).group(1).lower()
        label = caption or alt or heading or name
        found.append((score, i, Candidate(
            source="web", title=label[:200], image_url=src, page_url=page_url, preview_url=src, width=w, height=h,
            mime=_MIME.get(ext, "image/jpeg"), licence=f"© {host}", author=host,
            description=f"{caption or alt} | {heading} | {title}"[:300], rank=rank,
            meta={"page": title[:120], "match": round(score, 2)})))
    found.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, _, c in found[:PER_PAGE]]


async def _page(c: httpx.AsyncClient, url: str, query: str, rank: int) -> list[Candidate]:
    try:
        if not await allowed(c, url):
            log.info("web page %s: robots.txt disallows it", url)
            return []
        r = await c.get(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"}, timeout=PAGE_TIMEOUT_S)
        r.raise_for_status()
        if "html" not in r.headers.get("content-type", "") or len(r.content) > MAX_PAGE_BYTES:
            return []
        return await asyncio.to_thread(page_figures, r.text, str(r.url), query, rank)
    except httpx.HTTPError as e:
        log.info("web page %s: %s", url[:80], type(e).__name__)
        return []


async def web_figures(c: httpx.AsyncClient, query: str, pages: int = MAX_PAGES) -> list[Candidate]:
    """Pictures named by the query on the first result pages, interleaved by page (best page first)."""
    urls = await search_pages(c, query, pages)
    tasks = [asyncio.create_task(_page(c, u, query, i)) for i, u in enumerate(urls)]
    done, late = await asyncio.wait(tasks, timeout=PAGE_TIMEOUT_S + 2) if tasks else (set(), set())
    for t in late:  # a slow page must not cost the others their pictures
        t.cancel()
    lists = [t.result() if t in done and not t.exception() else [] for t in tasks]
    out: list[Candidate] = []
    for k in range(max((len(x) for x in lists), default=0)):
        out += [x[k] for x in lists if k < len(x)]
    log.info("web pages for %r: %d page(s), %d named picture(s)", query, len(urls), len(out))
    return out
