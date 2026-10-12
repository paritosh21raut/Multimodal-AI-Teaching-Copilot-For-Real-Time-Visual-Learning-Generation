"""Build tests/fixtures/notes/reference_biology.pdf (F-012): three pages of study notes with real figures + captions.

The figures are real images from the image cache (Wikimedia, downscaled); Edge prints the HTML to PDF as for a web
link, so the PDF has real image objects and real text, like the teacher's own material. Run once; the PDF is a fixture.
    .venv/Scripts/python tools/make_reference_fixture.py
"""
from __future__ import annotations

import asyncio
import base64
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from copilot.notes.convert import html_pdf  # noqa: E402

CACHE = ROOT / "data" / "cache" / "images"
OUT = ROOT / "tests" / "fixtures" / "notes" / "reference_biology.pdf"

PAGES = [
    ("The human heart", "07261fcf8315ea6f", "Figure 1: Labelled diagram of the human heart showing the four chambers",
     "The heart is a muscular organ that pumps blood through the body. It has four chambers: the right atrium, the "
     "right ventricle, the left atrium and the left ventricle. The sinoatrial node starts each heartbeat; the "
     "sinoatrial node is the natural pacemaker. Valves stop blood flowing backwards. The septum separates the left "
     "and right sides of the heart."),
    ("The chloroplast", "1c3c0c8a8034e604", "Figure 2: Structure of a chloroplast with thylakoid stacks (grana)",
     "Photosynthesis takes place in the chloroplast. Chlorophyll in the thylakoid membranes absorbs light energy. "
     "The light reactions happen in the thylakoid; the Calvin cycle happens in the stroma and fixes carbon dioxide "
     "into glucose. Chlorophyll reflects green light, which is why leaves look green. Each thylakoid stack is a granum."),
    ("The human skeleton", "59c1a709388ed878", "Figure 3: The human skeleton, front view",
     "The adult human skeleton has 206 bones. It supports the body, protects organs such as the brain and the heart, "
     "and works with muscles to move the body. Red bone marrow makes blood cells. The femur is the longest bone."),
]


def data_url(image_id: str, width: int) -> str:
    img = Image.open(CACHE / f"{image_id}.jpg").convert("RGB")
    img.thumbnail((width, width))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def page_html() -> str:
    parts = []
    for title, image_id, caption, text in PAGES:
        parts.append(f"<section><h1>{title}</h1><p>{text}</p>"
                     f"<figure><img src='{data_url(image_id, 520)}'><figcaption>{caption}</figcaption></figure>"
                     f"</section>")
    return ("<html><head><style>@page{size:A4;margin:18mm}body{font:12pt Georgia,serif}"
            "section{page-break-after:always}img{width:120mm;display:block;margin:6mm auto 2mm}"
            "figcaption{text-align:center;font-style:italic}</style></head><body>" + "".join(parts) + "</body></html>")


async def main() -> None:
    OUT.write_bytes(await html_pdf(page_html()))
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    asyncio.run(main())
