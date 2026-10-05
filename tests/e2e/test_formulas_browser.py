"""F-007a in a real browser (Edge via Playwright): KaTeX formulas, fallback, chemical subscripts in text.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_formulas_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.presentation.mathtext import chem_parts, to_latex  # noqa: E402
from copilot.presentation.spec import FormulaBlock, Item, PointsBlock, SlideSpec, Variable  # noqa: E402

pytestmark = pytest.mark.browser

EXPRESSIONS = [  # recorded model outputs + physics/maths
    "6CO2 + 6H2O + light → C6H12O6 + 6O2",
    "carbon dioxide plus water, in the presence of sunlight and chlorophyll, gives glucose plus oxygen",
    "Cardiac Output = Heart Rate × Stroke Volume",
    "KE = 1/2 m v^2", "speed = distance / time", "λ = v / f", "Δx = v Δt", "a² + b² = c²",
    "profit = income − cost & tax", "100% efficiency = output / input",
]
TOKENS = ["CO2", "H2O", "C6H12O6", "Fe2O3", "2H2O", "O2", "S8", "B12", "N95", "H1N1", "A4", "COVID19", "U2", "NaCl",
          "MP3", "CO", "H2SO4", "Ca3P2", "Cl2", "O9"]


def formula_slide(sid, expr, variables=()):
    return SlideSpec(id=sid, title="Formula", layout="formula", blocks=[FormulaBlock(
        id="f", latex=to_latex(expr), spoken=expr,
        variables=[Variable(symbol=s, meaning=m, latex=to_latex(s)) for s, m in variables])])


async def test_every_converted_formula_renders_with_katex():
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        for n, expr in enumerate(EXPRESSIONS):
            assert to_latex(expr), expr
            sid = f"f{n}"
            await h.deck.add(formula_slide(sid, expr, [("CO2", "carbon dioxide"), ("v", "speed")]))
            await h.settle()
            await wait_for_slide(page, sid)
            info = await page.evaluate("""() => {
                const eq = document.querySelector('.slide:not(.is-leaving) .formula-eq');
                const box = eq.getBoundingClientRect(), stage = document.querySelector('.stage').getBoundingClientRect();
                return {katex: !!eq.querySelector('.katex'), error: !!document.querySelector('.katex-error'),
                        fallback: !!eq.querySelector('.tex-fallback'), vars: document.querySelectorAll('.formula-vars .katex').length,
                        inside: box.left >= stage.left - 1 && box.right <= stage.right + 1};
            }""")
            assert info == {"katex": True, "error": False, "fallback": False, "vars": 2, "inside": True}, (expr, info)
        assert page.errors == []


async def test_unrenderable_formula_shows_the_spoken_text():
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        spec = SlideSpec(id="bad", title="Formula", layout="formula", blocks=[FormulaBlock(
            id="f", latex=r"\frac{a}{", spoken="a over b")])
        await h.deck.add(spec)
        await h.settle()
        await wait_for_slide(page, "bad")
        text = await page.evaluate("() => document.querySelector('.formula-eq .tex-fallback')?.textContent")
        assert text == "a over b"
        assert not [e for e in page.errors if "katex" not in e.lower()]  # only the logged KaTeX warning, no failure


async def test_chemical_formulas_in_text_get_subscripts_and_match_python_rules():
    async with display_harness() as h, browser_page(f"{h.url}/display") as page:
        await h.deck.add(SlideSpec(id="chem", title="Gases in CO2 and H2O", layout="key_points", blocks=[
            PointsBlock(id="p", items=[Item(id="a", text="Plants take in CO2 and give out O2"),
                                       Item(id="b", text="Vitamin B12 and N95 masks stay as written")])]))
        await h.settle()
        await wait_for_slide(page, "chem")
        subs = await page.evaluate("""() => [...document.querySelectorAll('.slide-title sub, .point sub')]
                                       .map(s => s.parentElement.textContent.trim() && s.textContent)""")
        assert subs == ["2", "2", "2", "2"]  # title CO2 H2O, point CO2 O2; nothing in B12/N95
        texts = await page.evaluate("() => [...document.querySelectorAll('.point')].map(p => p.textContent.trim())")
        assert texts[1].endswith("Vitamin B12 and N95 masks stay as written")
        js = await page.evaluate("""async (tokens) => {
            const m = await import('/web/shared/rich.js');
            return tokens.map(t => { const r = m.chemParts(t); return r ? r.parts : null; });
        }""", TOKENS)
        py = [[list(p) for p in parts] if (parts := chem_parts(t)) else None for t in TOKENS]
        assert js == py
        assert page.errors == []
