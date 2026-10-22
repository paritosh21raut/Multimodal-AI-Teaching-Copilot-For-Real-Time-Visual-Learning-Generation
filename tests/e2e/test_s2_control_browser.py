"""F-014 S2 part A in Edge: the user's /control issues of 2026-10-18.

1. The dock's Simulation button opened an "empty" list: the compact dock's rule hid every <span> in the group, the
   picker's menu rows too (8 rows in the DOM, no names visible) at 1536 px. The list must show every template.
2. The Values popover's slot names were faint: the popover's background follows the slide theme (the preview's
   data-theme) while its text inherited the /control page's ink. Contrast is checked in all four theme pairs.
3. The dock shows icon + name; icons only while My Notes is expanded. The Back to slides swap keeps working.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_s2_control_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from copilot.simulation.templates import ALL  # noqa: E402
from tests.e2e.test_simulation_browser import SIM, attr, lecture, sim_of  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "app"
PDF = PROJECT_ROOT / "tests" / "fixtures" / "notes" / "photosynthesis_notes.pdf"
SIZES = [(1536, 730), (1920, 1080)]

# the visible text of the dock's own buttons (a hidden <span> has no box)
DOCK_LABELS = """() => [...document.querySelectorAll('.dock .group > button, .dock .group > .menu-wrap > button, .dock > button')]
  .map((b) => { const s = b.querySelector('span'); return s ? [s.textContent, s.getBoundingClientRect().width] : null; })
  .filter(Boolean)"""
ROWS = """() => [...document.querySelectorAll('.sim-picker .eq-row')].map((r) => {
  const b = r.querySelector('b'); const box = b.getBoundingClientRect(); return [b.textContent, box.width, box.height]; })"""
# WCAG contrast of each Values row name against the popover's background
CONTRAST = """() => {
  const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = (c) => { const v = rgb(c).map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const bg = getComputedStyle(document.querySelector('.sim-values')).backgroundColor;
  return [...document.querySelectorAll('.sim-values .sim-row > span')].map((s) => {
    const a = lum(getComputedStyle(s).color), b = lum(bg);
    return [s.textContent.trim(), (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)]; });
}"""


@pytest.mark.parametrize("size", SIZES)
async def test_the_simulation_list_shows_every_template(size):
    async with display_harness() as h:
        await lecture(h, [])
        async with browser_page(f"{h.url}/control", *size) as control, browser_page(f"{h.url}/display") as display:
            await wait_for_slide(control, h.deck.live.id)
            await control.click(".sim-picker > button")
            await control.wait_for_function(f"() => document.querySelectorAll('.sim-picker .eq-row').length === {len(ALL)}")
            rows = await control.evaluate(ROWS)
            assert [r[0] for r in rows] == [t.name for t in ALL]
            assert all(w > 40 and hgt > 10 for _, w, hgt in rows), rows  # the names are visible, not only in the DOM
            ART.mkdir(parents=True, exist_ok=True)
            await control.screenshot(path=str(ART / f"s2_sim_list_{size[0]}.png"))
            await control.click(".sim-picker .eq-row:has-text('Travelling wave')")
            await h.until(lambda: sim_of(h.deck).template == "wave")
            assert sim_of(h.deck).template == "wave"
            await display.wait_for_selector(SIM)
            assert await attr(display, "data-template") == "wave"
            assert not control.errors and not display.errors, (control.errors, display.errors)


@pytest.mark.parametrize("size", SIZES)
async def test_the_dock_shows_names_and_icons_only_with_my_notes_expanded(tmp_path, size):
    async with display_harness(notes_dir=tmp_path / "notes") as h:
        await lecture(h, [])
        async with browser_page(f"{h.url}/control", *size) as c:
            await wait_for_slide(c, h.deck.live.id)
            await c.wait_for_timeout(400)
            assert "compact" not in await c.get_attribute(".dock", "class")
            labels = await c.evaluate(DOCK_LABELS)
            names = [t for t, _ in labels]
            for want in ("Pause", "Blank", "Dark", "New slide", "Add point", "Equation", "Simulation", "End lecture"):
                assert want in names, names
            assert all(w > 0 for _, w in labels), labels
            assert await c.evaluate("document.documentElement.scrollWidth <= innerWidth")
            ART.mkdir(parents=True, exist_ok=True)
            await c.screenshot(path=str(ART / f"s2_dock_{size[0]}.png"))
            # My Notes open (not expanded): names stay; expanded: icons only, the tooltips keep the names
            await c.click(".tabs button[aria-label='My Notes']")
            await c.set_input_files(".notes input[type=file]", str(PDF))
            await c.wait_for_selector(".notes-page img", timeout=15000)
            await c.wait_for_timeout(300)
            assert "compact" not in await c.get_attribute(".dock", "class")
            await c.click(".notes-head button[aria-label='Wider notes']")
            await c.wait_for_selector(".dock.compact")
            middle = [(t, w) for t, w in await c.evaluate(DOCK_LABELS) if t not in ("Pause", "Paused")]
            assert all(w == 0 for _, w in middle if _ != "End lecture"), middle
            await c.screenshot(path=str(ART / f"s2_dock_{size[0]}_notes_wide.png"))
            # the Simulation list still shows its names in the compact dock (the original bug)
            await c.click(".sim-picker > button")
            rows = await c.evaluate(ROWS)
            assert len(rows) == len(ALL) and all(w > 40 for _, w, _h in rows), rows
            await c.keyboard.press("Escape")
            await c.click(".notes-head button[aria-label='Narrower notes']")
            await c.wait_for_function("() => !document.querySelector('.dock').classList.contains('compact')")
            assert not c.errors, c.errors


async def test_back_to_slides_swap_keeps_the_names():
    async with display_harness() as h:
        await lecture(h, ["Consider a block of mass 5 kg on a rough floor with mu equal to 0.2."])
        assert h.deck.sim_mode == h.deck.live.id
        async with browser_page(f"{h.url}/control", 1536, 730) as c:
            await c.wait_for_selector(".dock button.sim-end")
            await c.wait_for_timeout(300)
            assert "compact" not in await c.get_attribute(".dock", "class")
            assert "Back to slides" in [t for t, w in await c.evaluate(DOCK_LABELS) if w > 0]
            await c.click(".dock button.sim-end")
            await h.until(lambda: h.deck.sim_mode is None)
            assert h.deck.sim_mode is None
            await c.wait_for_selector(".sim-picker > button")
            assert not c.errors, c.errors


@pytest.mark.parametrize("slide_theme", ["light", "dark"])
@pytest.mark.parametrize("page_theme", ["light", "dark"])
async def test_values_names_are_readable_in_every_theme_pair(slide_theme, page_theme):
    async with display_harness(slide_theme) as h:
        await lecture(h, ["Consider a block of mass 5 kg on a rough floor with mu equal to 0.2.",
                          "We push it with a force of 20 newtons."])
        async with browser_page(f"{h.url}/control", 1600, 1000) as c:
            await wait_for_slide(c, h.deck.live.id)
            if page_theme == "dark":
                await c.click("button.page-theme")
                await c.wait_for_function("() => document.documentElement.dataset.theme === 'dark'")
            await c.wait_for_selector(".sim-svg")
            await c.click(".sim-bar button:has-text('Values')")
            await c.wait_for_selector(".sim-values .sim-row")
            ratios = await c.evaluate(CONTRAST)
            assert ratios and all(r >= 7 for _, r in ratios), ratios  # body text AAA: the names are the point
            ART.mkdir(parents=True, exist_ok=True)
            await c.locator(".sim-values").screenshot(path=str(ART / f"s2_values_{page_theme}_page_{slide_theme}_slide.png"))
            assert not c.errors, c.errors
