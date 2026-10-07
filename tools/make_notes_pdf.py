"""Make the teacher-notes PDF fixture (F-009): a teacher's own notes for the photosynthesis lecture, one topic per
page, written in the teacher's words (not the slides'), plus two pages about other things.

    .venv/Scripts/python tools/make_notes_pdf.py   -> tests/fixtures/notes/photosynthesis_notes.pdf
"""
from __future__ import annotations

import asyncio
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "notes" / "photosynthesis_notes.pdf"

PAGES = [
    ("Class 7 Biology — lesson plan", [
        "Period 3, 40 minutes. Bring a potted plant and a leaf for the class to look at.",
        "Attendance first. Collect the homework notebooks from last week.",
        "Remind the class about the field trip form due on Friday.",
    ]),
    ("1. Photosynthesis — meaning", [
        "Photosynthesis is the process by which green plants prepare their own food using sunlight.",
        "Break the word: photo = light, synthesis = putting together.",
        "Plants are autotrophs (producers); animals depend on them for food.",
    ]),
    ("2. What the plant needs", [
        "Four raw materials: sunlight, water, carbon dioxide and chlorophyll.",
        "Roots absorb water from the soil; xylem carries it up to the leaves.",
        "Carbon dioxide enters through stomata, the tiny pores on the underside of the leaf.",
        "Chlorophyll, the green pigment in chloroplasts, traps the light energy.",
    ]),
    ("3. Steps of the process", [
        "Step 1: chlorophyll absorbs light energy.",
        "Step 2: light energy splits water molecules into hydrogen and oxygen.",
        "Step 3: hydrogen combines with carbon dioxide to form glucose.",
        "Step 4: oxygen is given out as a by-product through the stomata.",
    ]),
    ("4. Word equation", [
        "Carbon dioxide + water --(sunlight, chlorophyll)--> glucose + oxygen.",
        "6CO2 + 6H2O -> C6H12O6 + 6O2 (only for the faster students).",
        "Glucose is stored as starch; iodine test turns it blue-black.",
    ]),
    ("5. Why it matters", [
        "Source of food for almost every living thing on Earth.",
        "Releases the oxygen we breathe; removes carbon dioxide from the air.",
        "Fossil fuels such as coal came from plants that stored the sun's energy long ago.",
    ]),
    ("6. Respiration (compare next class)", [
        "Respiration breaks down glucose to release energy; it happens day and night in all living cells.",
        "Glucose + oxygen -> carbon dioxide + water + energy: the reverse of photosynthesis.",
        "Homework: table comparing photosynthesis and respiration.",
    ]),
]

STYLE = """
@page { size: A4; margin: 22mm 20mm; }
body { font: 13pt/1.55 Georgia, 'Times New Roman', serif; color: #1b1b1b; }
section { page-break-after: always; }
section:last-child { page-break-after: auto; }
h1 { font: 700 20pt/1.2 'Segoe UI', sans-serif; color: #1d3f6e; border-bottom: 2px solid #1d3f6e; padding-bottom: 6px; }
li { margin: 10px 0; }
.foot { margin-top: 40px; font-size: 10pt; color: #777; }
"""


def html() -> str:
    body = "".join(
        f"<section><h1>{title}</h1><ul>{''.join(f'<li>{x}</li>' for x in items)}</ul>"
        f"<p class='foot'>My notes · page {i + 1}</p></section>"
        for i, (title, items) in enumerate(PAGES))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{STYLE}</style></head><body>{body}</body></html>"


async def main() -> None:
    from playwright.async_api import async_playwright

    OUT.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page()
        await page.set_content(html())
        await page.pdf(path=str(OUT), format="A4", print_background=True)
        await browser.close()
    print(OUT)


if __name__ == "__main__":
    asyncio.run(main())
