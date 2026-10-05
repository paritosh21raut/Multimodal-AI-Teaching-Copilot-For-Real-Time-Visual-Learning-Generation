"""Plain-text formula → LaTeX (F-007a). Cases include every formula the model produced in recorded sessions."""
import pytest

from copilot.presentation.mathtext import chem_parts, has_fraction, mark_math, to_latex, visible_length

CO2 = r"\text{CO}_{\text{2}}"
GLUCOSE = r"\text{C}_{\text{6}}\text{H}_{\text{12}}\text{O}_{\text{6}}"


@pytest.mark.parametrize("expr, latex", [
    # recorded model outputs
    ("CO2 + H2O → C6H12O6 + O2", CO2 + r" + \text{H}_{\text{2}}\text{O} \rightarrow " + GLUCOSE + r" + \text{O}_{\text{2}}"),
    ("6CO2 + 6H2O + light → C6H12O6 + 6O2",
     r"\text{6}\," + CO2 + r" + \text{6}\,\text{H}_{\text{2}}\text{O} + \text{light} \rightarrow " + GLUCOSE + r" + \text{6}\,\text{O}_{\text{2}}"),
    ("6CO2 plus 6H2O plus light gives us C6H12O6 plus 6O2",
     r"\text{6}\," + CO2 + r" + \text{6}\,\text{H}_{\text{2}}\text{O} + \text{light} \rightarrow " + GLUCOSE + r" + \text{6}\,\text{O}_{\text{2}}"),
    ("Cardiac Output = Heart Rate × Stroke Volume",
     r"\text{Cardiac Output} = \text{Heart Rate} \times \text{Stroke Volume}"),
    ("carbon dioxide plus water, in the presence of sunlight and chlorophyll, gives glucose plus oxygen",
     r"\text{carbon dioxide} + \text{water} \xrightarrow{\text{sunlight and chlorophyll}} \text{glucose} + \text{oxygen}"),
    # physics / maths
    ("F = ma", "F = m a"),
    ("F = m × a", r"F = m \times a"),
    ("v = u + at", "v = u + a t"),
    ("E = mc^2", "E = m c^{2}"),
    ("E = mc²", "E = m c^{2}"),
    ("a² + b² = c²", "a^{2} + b^{2} = c^{2}"),
    ("speed = distance / time", r"\text{speed} = \dfrac{\text{distance}}{\text{time}}"),
    ("P = F/A", r"P = \dfrac{F}{A}"),
    ("KE = 1/2 m v^2", r"\text{KE} = \dfrac{1}{2} m v^{2}"),
    ("λ = v / f", r"\lambda = \dfrac{v}{f}"),
    ("Δx = v Δt", r"\Delta x = v \Delta t"),
    ("2H2 + O2 -> 2H2O", r"\text{2}\,\text{H}_{\text{2}} + \text{O}_{\text{2}} \rightarrow \text{2}\,\text{H}_{\text{2}}\text{O}"),
    ("Ohm's law: V = I × R", r"V = I \times R"),
    ("x-ray energy = h × f", "\\text{x\u2010ray energy} = h \\times f"),
    ("8 − 3 = 5", "8 - 3 = 5"),
    # spoken (Indian English) forms; symbols or words decided per side of "="
    ("F equals m into a", r"F = m \times a"),
    ("Kinetic energy equals half m v squared", r"\text{Kinetic energy} = \dfrac{1}{2} m v^{2}"),
    ("Kinetic energy = 1/2 m v^2", r"\text{Kinetic energy} = \dfrac{1}{2} m v^{2}"),
    ("water turns into steam", r"\text{water turns into steam}"),
    # real model output (qwen, session 20261006-010822-cdb5): rendered as 1 over "2 mv" before the fix
    ("KE = 1/2 mv²", r"\text{KE} = \dfrac{1}{2} m v^{2}"),
    ("Speed = Distance / Time", r"\text{Speed} = \dfrac{\text{Distance}}{\text{Time}}"),
    ("speed = d / t", r"\text{speed} = \dfrac{d}{t}"),
    ("ice + heat → water", r"\text{ice} + \text{heat} \rightarrow \text{water}"),
    ("ice → water", r"\text{ice} \rightarrow \text{water}"),
])
def test_to_latex(expr, latex):
    assert to_latex(expr) == latex


def test_latex_input_is_kept_when_safe():
    assert to_latex(r"\frac{a}{b} = c") == r"\frac{a}{b} = c"
    assert to_latex(r"x^{2} + y_{1}") == r"x^{2} + y_{1}"
    assert to_latex(r"\frac{a}{b") == ""          # unbalanced
    assert to_latex(r"\href{http://x}{y}") == ""  # never a link on the projector


def test_text_is_escaped():
    assert to_latex("profit = income − cost & tax") == r"\text{profit} = \text{income} - \text{cost \& tax}"
    assert to_latex("efficiency = output / input × 100%").endswith(r"\times 100 \%")


def test_empty_and_overlong():
    assert to_latex("") == ""
    assert to_latex("x = " + "y + " * 200) == ""


@pytest.mark.parametrize("token, ok", [
    ("CO2", True), ("H2O", True), ("C6H12O6", True), ("Fe2O3", True), ("2H2O", True), ("O2", True), ("S8", True),
    ("B12", False), ("N95", False), ("H1N1", False), ("A4", False), ("COVID19", False), ("U2", False),
    ("NaCl", False), ("MP3", False), ("Mercury", False), ("CO", False),
])
def test_chemical_tokens(token, ok):
    assert (chem_parts(token) is not None) is ok


@pytest.mark.parametrize("expr, latex", [
    # user's live tests 2026-10-06 (resistors, voltage, power, quadratic, energy, neutralization)
    ("I1 = (R2 / (R1 + R2)) * I_total", r"I_{1} = \dfrac{R_{2}}{R_{1} + R_{2}} \times I_{\text{total}}"),
    ("V2 = (R2/(R1+R2))·Vin", r"V_{2} = \dfrac{R_{2}}{R_{1} + R_{2}} \cdot V_{\text{in}}"),
    ("I2 = (R1 / (R1 + R2)) × I", r"I_{2} = \dfrac{R_{1}}{R_{1} + R_{2}} \times I"),  # a current, not iodine
    ("1/R_eq = 1/R1 + 1/R2", r"\dfrac{1}{R_{\text{eq}}} = \dfrac{1}{R_{1}} + \dfrac{1}{R_{2}}"),
    ("R_eq = R1 + R2", r"R_{\text{eq}} = R_{1} + R_{2}"),
    ("P = I²R = V²/R", r"P = I^{2} R = \dfrac{V^{2}}{R}"),
    ("P equals I squared R or V squared by R", r"P = I^{2} R \quad\text{or}\quad \dfrac{V^{2}}{R}"),
    ("v equals w by q", r"v = \dfrac{w}{q}"),
    ("V = ΔU / q", r"V = \dfrac{\Delta U}{q}"),
    ("τ = RC", r"\tau = R C"),
    ("x = (-b ± √(b² - 4ac)) / 2a", r"x = \dfrac{- b \pm \sqrt{b^{2} - 4 a c}}{2 a}"),
    ("x squared minus 5x plus 6 equals 0", r"x^{2} - 5 x + 6 = 0"),
    ("x=3 or x=2", r"x = 3 \quad\text{or}\quad x = 2"),
    ("KE = ½ m v^2", r"\text{KE} = \dfrac{1}{2} m v^{2}"),
    ("PE = m g h", r"\text{PE} = m g h"),
    ("H⁺ + OH⁻ → H₂O", r"\text{H}^{+} + \text{OH}^{-} \rightarrow \text{H}_{\text{2}}\text{O}"),
    ("HCl + NaOH → NaCl + H2O", r"\text{HCl} + \text{NaOH} \rightarrow \text{NaCl} + \text{H}_{\text{2}}\text{O}"),
])
def test_to_latex_live_formulas(expr, latex):
    assert to_latex(expr) == latex


@pytest.mark.parametrize("text, marked", [
    ("has the form ax² + bx + c = 0", r"has the form \(a x^{2} + b x + c = 0\)"),
    ("If the discriminant (b²-4ac) is negative, there are no real solutions",
     r"If the discriminant (\(b^{2} - 4 a c\)) is negative, there are no real solutions"),
    ("Solve x²-5x+6=0 using the quadratic formula → x=3 or x=2",
     r"Solve \(x^{2} - 5 x + 6 = 0\) using the quadratic formula → \(x = 3\) or \(x = 2\)"),
    ("H⁺ + OH⁻ → H₂O", r"\(\text{H}^{+} + \text{OH}^{-} \rightarrow \text{H}_{\text{2}}\text{O}\)"),
    ("Mechanical energy = potential energy + kinetic energy",
     r"\(\text{Mechanical energy} = \text{potential energy} + \text{kinetic energy}\)"),
    ("v = u + a·t", r"\(v = u + a \cdot t\)"),
    ("Example: CO2 + H2O → glucose", r"Example: \(\text{CO}_{\text{2}} + \text{H}_{\text{2}}\text{O} \rightarrow \text{glucose}\)"),
    ("G = 1 / R", r"\(G = \dfrac{1}{R}\)"),
    # exact model text (U+2011 non-breaking hyphens), quadratic live test: was left as plain text
    ("Solve x²‑5x+6=0 using the quadratic formula → x=3 or x=2",
     r"Solve \(x^{2} - 5 x + 6 = 0\) using the quadratic formula → \(x = 3\) or \(x = 2\)"),
    ("If the discriminant (b²‑4ac) is negative, there are no real solutions",
     r"If the discriminant (\(b^{2} - 4 a c\)) is negative, there are no real solutions"),
    # spoken equations the model wrote as points (electricity live test)
    ("V2 equals R2 upon R1 plus R2 times Vin",  # spoken: the denominator runs to "times"
     r"\(V_{2} = \dfrac{R_{2}}{R_{1} + R_{2}} \times V_{\text{in}}\)"),
    ("Force equals mass multiplied by acceleration", r"\(\text{Force} = \text{mass} \times \text{acceleration}\)"),
    ("Voltage equals work done per unit charge", ""),
    # no equation: left alone (units, ions in prose, plain statements)
    ("a: Acceleration (m/s²)", ""), ("Unit: metre per second squared (m/s²)", ""), ("Acid provides H⁺ ions", ""),
    ("Car travels 100 m in 5 s, speed = 20 m/s", ""), ("Plants take in CO2", ""), ("F: Force (Newtons)", ""),
    ("Voltage is the work done per unit charge = energy per coulomb of charge moved", ""),
])
def test_mark_math(text, marked):
    assert mark_math(text) == marked


def test_visible_length_and_fraction():
    latex = to_latex("speed = distance / time")
    assert has_fraction(latex)
    assert visible_length(latex) < len("speed = distance / time")
    assert visible_length(to_latex("CO2 + H2O → C6H12O6 + O2")) <= len("CO2 + H2O → C6H12O6 + O2")
