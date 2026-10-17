"""Write tests/fixtures/notes/drawn_figures.pdf (F-013 S4): a datasheet page in miniature, drawn with vector paths
only (no image objects), like the ESP-WROOM-32 datasheet in the teacher's notes.

    .venv/Scripts/python tools/make_figure_fixture.py

Page 1 (A4): a section heading; a block diagram (boxes, wires, labels) with "Figure 1: Block diagram of a
microcontroller" under it; a sentence about it ("Figure 1 shows ..."); a framed "Note:" box; a ruled table with
"Table 1: Pin functions" over it. Page 2: a reset circuit drawn inside a form XObject scaled 1.4 (pdfium reports such
paths in the form's own space), captioned "Figure 2: Reset circuit".
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "notes" / "drawn_figures.pdf"


def text(x: float, y: float, s: str, size: int = 10) -> str:
    return f"BT /F1 {size} Tf {x} {y} Td ({s}) Tj ET\n"


def page1() -> str:
    c = text(56, 800, "3. Architecture", 14)
    # block diagram: 6 boxes + wires, y 520..740
    boxes = [(80, 680, 110, 50, "CPU"), (240, 680, 110, 50, "Flash"), (400, 680, 110, 50, "SRAM"),
             (80, 560, 110, 50, "GPIO"), (240, 560, 110, 50, "ADC"), (400, 560, 110, 50, "UART")]
    for x, y, w, h, label in boxes:
        c += f"{x} {y} {w} {h} re S\n" + text(x + 30, y + 20, label)
    c += "70 540 450 210 re S\n"  # the chip outline around the blocks
    for x1, y1, x2, y2 in [(190, 705, 240, 705), (350, 705, 400, 705), (135, 680, 135, 610), (295, 680, 295, 610),
                           (455, 680, 455, 610), (190, 585, 240, 585), (350, 585, 400, 585)]:
        c += f"{x1} {y1} m {x2} {y2} l S\n"
    c += text(180, 515, "Figure 1: Block diagram of a microcontroller", 11)
    c += text(56, 480, "Figure 1 shows the blocks of the chip and how the bus joins them.")
    # a framed note: text in a box, not a drawing
    c += "56 380 480 70 re S\n"
    c += text(66, 430, "Note: the ADC shares its pins with GPIO port A, so a pin used for analog input")
    c += text(66, 412, "cannot be a digital output at the same time. Configure the port before reading.")
    # a ruled table under its caption
    c += text(220, 340, "Table 1: Pin functions", 11)
    for i in range(6):
        y = 320 - i * 24
        c += f"56 {y} m 536 {y} l S\n"
    for x in (56, 200, 536):
        c += f"{x} 320 m {x} 200 l S\n"
    for i, (a, b) in enumerate([("PA0", "ADC input"), ("PA1", "GPIO"), ("PA2", "UART TX"), ("PA3", "UART RX")]):
        c += text(66, 302 - i * 24, a) + text(210, 302 - i * 24, b)
    return c


def page2_form() -> str:
    c = ""
    for x, y, w, h in [(40, 40, 60, 40), (160, 40, 60, 40)]:
        c += f"{x} {y} {w} {h} re S\n"
    for x1, y1, x2, y2 in [(10, 60, 40, 60), (100, 60, 160, 60), (220, 60, 260, 60), (190, 40, 190, 10),
                           (70, 40, 70, 10), (60, 10, 200, 10), (120, 60, 120, 90), (110, 90, 130, 90),
                           (260, 60, 260, 95), (250, 95, 270, 95)]:
        c += f"{x1} {y1} m {x2} {y2} l S\n"
    c += text(52, 56, "VCC", 8) + text(170, 56, "RESET", 8)
    return c


def build() -> bytes:
    p1 = page1().encode("latin-1")
    form = page2_form().encode("latin-1")
    p2 = (text(56, 800, "4. Power", 14) + "q 1.4 0 0 1.4 120 500 cm /Fm1 Do Q\n"
          + text(230, 470, "Figure 2: Reset circuit", 11)).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(p1) + p1 + b"endstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 7 0 R >> "
        b"/XObject << /Fm1 8 0 R >> >> /Contents 6 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(p2) + p2 + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 300 120] /Resources << /Font << /F1 7 0 R >> >> /Length %d >>"
        b"\nstream\n" % len(form) + form + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


if __name__ == "__main__":
    OUT.write_bytes(build())
    print(OUT)
