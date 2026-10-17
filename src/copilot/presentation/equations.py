"""Named standard equations (F-013 S3, C10): a local, checked library, 0 tokens.

A teacher names "Schrödinger's time-dependent equation" or "Maxwell's equations" but cannot speak them (test16: a
whole lecture on the equation, no equation on screen). When a transcript line names one (or says "write / show the
equation" while the slide is about one), the presentation engine adds its standard form to the slide, marked
"standard form"; the formula the teacher says always wins (no library form when the unit has its own formula).
/control "Show equation" adds any entry by name.

Every LaTeX string here renders in KaTeX 0.16 (tests/browser/test_equations_render.py). Names are matched on the
normalised line (lower case, accents and apostrophes dropped), aliases include Whisper's spellings. A family
(Maxwell, Schrödinger, equations of motion) has a generic name that shows its default members; a specific form
named in the same line wins ("time-independent Schrödinger equation").
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Equation:
    id: str
    name: str                                 # shown above the equation ("Gauss's law (electric)")
    latex: str
    plain: str                                # text form (search, dedupe, the model's way of writing it)
    legend: tuple[tuple[str, str, str], ...]  # (symbol latex, symbol text, meaning)
    aliases: tuple[str, ...]                  # regexes on the normalised line
    family: str = ""
    context: str = ""                         # a regex the unit or slide must also match (ambiguous names)
    search: str = ""                          # extra words for /control search


def _eq(id, name, latex, plain, legend, aliases, family="", context="", search="") -> Equation:
    return Equation(id, name, latex, plain, tuple(legend), tuple(aliases), family, context, search)


_POSS = r"(?:'?s)?"  # "maxwell", "maxwell's", "maxwells"
_SCHRO = r"s?ch?ro[e]?d[ie]ng[ae]r" + _POSS  # schrodinger / shrodinger / schroedinger / schrodingers

LIBRARY: tuple[Equation, ...] = (
    # ---- quantum ----------------------------------------------------------------------------------------------
    _eq("schrodinger_td", "Schrödinger equation (time-dependent)",
        r"i\hbar\,\dfrac{\partial \Psi}{\partial t} = \hat{H}\,\Psi", "iħ ∂Ψ/∂t = ĤΨ",
        [(r"\Psi", "Ψ", "wave function"), (r"\hbar", "ħ", "reduced Planck constant"),
         (r"\hat{H}", "Ĥ", "Hamiltonian operator"), ("t", "t", "time")],
        [rf"time[- ]?dependent {_SCHRO}(?: wave)? equation", rf"{_SCHRO}(?: wave)? equation,? (?:the )?time[- ]?dependent"],
        family="schrodinger", search="quantum wave function"),
    _eq("schrodinger_ti", "Schrödinger equation (time-independent)",
        r"\hat{H}\,\psi = E\,\psi", "Ĥψ = Eψ",
        [(r"\psi", "ψ", "wave function"), (r"\hat{H}", "Ĥ", "Hamiltonian operator"), ("E", "E", "energy")],
        [rf"time[- ]?independent {_SCHRO}(?: wave)? equation", rf"{_SCHRO}(?: wave)? equation,? (?:the )?time[- ]?independent"],
        family="schrodinger", search="quantum stationary state"),
    _eq("de_broglie", "de Broglie wavelength", r"\lambda = \dfrac{h}{p} = \dfrac{h}{m v}", "λ = h/p = h/(mv)",
        [(r"\lambda", "λ", "wavelength"), ("h", "h", "Planck constant"), ("p", "p", "momentum")],
        [r"de ?broglie" + _POSS + r" (?:equation|relation|wavelength|hypothesis)"], search="matter wave"),
    _eq("heisenberg", "Heisenberg uncertainty principle", r"\Delta x\,\Delta p \geq \dfrac{\hbar}{2}", "Δx Δp ≥ ħ/2",
        [(r"\Delta x", "Δx", "uncertainty in position"), (r"\Delta p", "Δp", "uncertainty in momentum"),
         (r"\hbar", "ħ", "reduced Planck constant")],
        [r"(?:heisenberg" + _POSS + r" )?uncertainty principle"], search="quantum"),
    _eq("planck", "Planck's equation", r"E = h\nu", "E = hν",
        [("E", "E", "energy of a photon"), ("h", "h", "Planck constant"), (r"\nu", "ν", "frequency")],
        [r"planck" + _POSS + r" (?:equation|relation|law)"], search="photon energy quantum"),
    _eq("photoelectric", "Einstein's photoelectric equation", r"h\nu = \phi + K_{\max}", "hν = φ + K_max",
        [(r"h\nu", "hν", "photon energy"), (r"\phi", "φ", "work function"),
         (r"K_{\max}", "K_max", "maximum kinetic energy of the electron")],
        [r"einstein" + _POSS + r" photo ?electric equation", r"photo ?electric equation"], search="work function"),
    _eq("mass_energy", "Mass-energy equivalence", r"E = m c^{2}", "E = mc²",
        [("E", "E", "energy"), ("m", "m", "mass"), ("c", "c", "speed of light")],
        [r"mass[- ]energy (?:equivalence|relation|equation)", r"einstein" + _POSS + r" (?:mass[- ]energy )?(?:equation|relation)(?! of photo)"],
        search="relativity"),
    _eq("rydberg", "Rydberg formula",
        r"\dfrac{1}{\lambda} = R_{H}\left(\dfrac{1}{n_{1}^{2}} - \dfrac{1}{n_{2}^{2}}\right)", "1/λ = R(1/n₁² − 1/n₂²)",
        [(r"\lambda", "λ", "wavelength"), (r"R_{H}", "R_H", "Rydberg constant"), (r"n_{1}, n_{2}", "n₁, n₂", "energy levels")],
        [r"rydberg" + _POSS + r" (?:formula|equation)"], search="hydrogen spectrum"),
    # ---- electromagnetism: Maxwell ----------------------------------------------------------------------------
    _eq("gauss_e", "Gauss's law (electric)", r"\nabla \cdot \vec{E} = \dfrac{\rho}{\varepsilon_{0}}", "∇·E = ρ/ε₀",
        [(r"\vec{E}", "E", "electric field"), (r"\rho", "ρ", "charge density"),
         (r"\varepsilon_{0}", "ε₀", "permittivity of free space")],
        [r"gauss" + _POSS + r" law(?! (?:for|of) magnetism)(?! in magnetism)"], family="maxwell", search="maxwell"),
    _eq("gauss_b", "Gauss's law for magnetism", r"\nabla \cdot \vec{B} = 0", "∇·B = 0",
        [(r"\vec{B}", "B", "magnetic field")],
        [r"gauss" + _POSS + r" law (?:for|of|in) magnetism"], family="maxwell", search="maxwell monopole"),
    _eq("faraday", "Faraday's law", r"\nabla \times \vec{E} = -\dfrac{\partial \vec{B}}{\partial t}", "∇×E = −∂B/∂t",
        [(r"\vec{E}", "E", "electric field"), (r"\vec{B}", "B", "magnetic field"), ("t", "t", "time")],
        [r"faraday" + _POSS + r" law(?: of (?:electromagnetic )?induction)?"], family="maxwell", search="maxwell induction"),
    _eq("ampere", "Ampère–Maxwell law",
        r"\nabla \times \vec{B} = \mu_{0}\vec{J} + \mu_{0}\varepsilon_{0}\dfrac{\partial \vec{E}}{\partial t}",
        "∇×B = μ₀J + μ₀ε₀ ∂E/∂t",
        [(r"\vec{B}", "B", "magnetic field"), (r"\vec{J}", "J", "current density"),
         (r"\mu_{0}", "μ₀", "permeability of free space"), (r"\varepsilon_{0}", "ε₀", "permittivity of free space")],
        [r"amp[eè]re" + _POSS + r"(?:[- ]maxwell)? (?:circuital )?law"], family="maxwell", search="maxwell"),
    _eq("gauss_e_int", "Gauss's law (integral form)", r"\oint \vec{E} \cdot d\vec{A} = \dfrac{Q}{\varepsilon_{0}}",
        "∮E·dA = Q/ε₀",
        [(r"\vec{E}", "E", "electric field"), ("Q", "Q", "enclosed charge"), (r"\varepsilon_{0}", "ε₀", "permittivity of free space")],
        [r"gauss" + _POSS + r" law in (?:the )?integral form", r"integral form of gauss" + _POSS + r" law"],
        family="maxwell_int", search="maxwell flux"),
    _eq("coulomb", "Coulomb's law", r"F = k\,\dfrac{q_{1} q_{2}}{r^{2}}", "F = k q₁q₂/r²",
        [("F", "F", "force between the charges"), ("k", "k", "Coulomb constant"), (r"q_{1}, q_{2}", "q₁, q₂", "charges"),
         ("r", "r", "distance between them")],
        [r"coulomb" + _POSS + r" law"], search="electrostatic force"),
    _eq("ohm", "Ohm's law", r"V = I R", "V = IR",
        [("V", "V", "voltage"), ("I", "I", "current"), ("R", "R", "resistance")],
        [r"ohm" + _POSS + r" law"], search="resistance current voltage"),
    _eq("lorentz", "Lorentz force", r"\vec{F} = q\left(\vec{E} + \vec{v} \times \vec{B}\right)", "F = q(E + v×B)",
        [("q", "q", "charge"), (r"\vec{E}", "E", "electric field"), (r"\vec{v}", "v", "velocity"), (r"\vec{B}", "B", "magnetic field")],
        [r"lorentz" + _POSS + r" force(?: (?:law|equation))?"], search="magnetic force"),
    # ---- mechanics ---------------------------------------------------------------------------------------------
    _eq("newton_2", "Newton's second law", r"\vec{F} = m\,\vec{a}", "F = ma",
        [("F", "F", "net force"), ("m", "m", "mass"), ("a", "a", "acceleration")],
        [r"newton" + _POSS + r" second law", r"second law of (?:motion|newton)"], search="force mass acceleration"),
    _eq("newton_3", "Newton's third law", r"\vec{F}_{AB} = -\vec{F}_{BA}", "F_AB = −F_BA",
        [(r"\vec{F}_{AB}", "F_AB", "force of A on B"), (r"\vec{F}_{BA}", "F_BA", "force of B on A")],
        [r"newton" + _POSS + r" third law", r"third law of (?:motion|newton)"], search="action reaction"),
    _eq("gravitation", "Newton's law of gravitation", r"F = G\,\dfrac{m_{1} m_{2}}{r^{2}}", "F = G m₁m₂/r²",
        [("F", "F", "gravitational force"), ("G", "G", "gravitational constant"), (r"m_{1}, m_{2}", "m₁, m₂", "masses"),
         ("r", "r", "distance between their centres")],
        [r"(?:universal )?law of (?:universal )?gravitation", r"newton" + _POSS + r" law of gravity"], search="gravity"),
    _eq("motion_1", "First equation of motion", r"v = u + a t", "v = u + at",
        [("v", "v", "final velocity"), ("u", "u", "initial velocity"), ("a", "a", "acceleration"), ("t", "t", "time")],
        [r"first equation of motion"], family="motion", search="kinematics"),
    _eq("motion_2", "Second equation of motion", r"s = u t + \tfrac{1}{2} a t^{2}", "s = ut + ½at²",
        [("s", "s", "displacement"), ("u", "u", "initial velocity"), ("a", "a", "acceleration"), ("t", "t", "time")],
        [r"second equation of motion"], family="motion", search="kinematics"),
    _eq("motion_3", "Third equation of motion", r"v^{2} = u^{2} + 2 a s", "v² = u² + 2as",
        [("v", "v", "final velocity"), ("u", "u", "initial velocity"), ("a", "a", "acceleration"), ("s", "s", "displacement")],
        [r"third equation of motion"], family="motion", search="kinematics"),
    _eq("hooke", "Hooke's law", r"F = -k x", "F = −kx",
        [("F", "F", "restoring force"), ("k", "k", "spring constant"), ("x", "x", "extension")],
        [r"hooke" + _POSS + r" law"], search="spring elasticity"),
    _eq("bernoulli", "Bernoulli's equation", r"P + \tfrac{1}{2}\rho v^{2} + \rho g h = \text{constant}",
        "P + ½ρv² + ρgh = constant",
        [("P", "P", "pressure"), (r"\rho", "ρ", "density"), ("v", "v", "flow speed"), ("h", "h", "height")],
        [r"bernoulli" + _POSS + r" (?:equation|principle|theorem)"], search="fluid flow pressure"),
    _eq("continuity", "Continuity equation (fluid flow)", r"A_{1} v_{1} = A_{2} v_{2}", "A₁v₁ = A₂v₂",
        [(r"A_{1}, A_{2}", "A₁, A₂", "cross-section areas"), (r"v_{1}, v_{2}", "v₁, v₂", "flow speeds")],
        [r"(?:equation of continuity|continuity equation)"], context=r"fluid|flow|pipe|liquid|mass flow",
        search="fluid flow rate"),
    _eq("navier_stokes", "Navier–Stokes equation (incompressible)",
        r"\rho\left(\dfrac{\partial \vec{v}}{\partial t} + (\vec{v} \cdot \nabla)\vec{v}\right) = -\nabla p + \mu \nabla^{2}\vec{v} + \vec{f}",
        "ρ(∂v/∂t + (v·∇)v) = −∇p + μ∇²v + f",
        [(r"\vec{v}", "v", "flow velocity"), ("p", "p", "pressure"), (r"\mu", "μ", "viscosity"), (r"\vec{f}", "f", "body force per volume")],
        [r"navier[- ]?stokes?(?: equations?)?"], search="fluid dynamics viscosity"),
    # ---- thermodynamics / gases --------------------------------------------------------------------------------
    _eq("ideal_gas", "Ideal gas equation", r"P V = n R T", "PV = nRT",
        [("P", "P", "pressure"), ("V", "V", "volume"), ("n", "n", "amount of gas (moles)"), ("T", "T", "temperature")],
        [r"ideal gas (?:equation|law)", r"(?:gas equation|equation of state)(?= .*gas)"], search="gas law"),
    _eq("boyle", "Boyle's law", r"P_{1} V_{1} = P_{2} V_{2}", "P₁V₁ = P₂V₂",
        [("P", "P", "pressure"), ("V", "V", "volume")], [r"boyle" + _POSS + r" law"], search="gas law"),
    _eq("charles", "Charles's law", r"\dfrac{V_{1}}{T_{1}} = \dfrac{V_{2}}{T_{2}}", "V₁/T₁ = V₂/T₂",
        [("V", "V", "volume"), ("T", "T", "temperature (K)")], [r"charles" + _POSS + r" law"], search="gas law"),
    _eq("thermo_1", "First law of thermodynamics", r"\Delta U = Q - W", "ΔU = Q − W",
        [(r"\Delta U", "ΔU", "change in internal energy"), ("Q", "Q", "heat added"), ("W", "W", "work done by the system")],
        [r"first law of thermodynamics"], search="internal energy heat work"),
    _eq("gibbs", "Gibbs free energy", r"\Delta G = \Delta H - T\,\Delta S", "ΔG = ΔH − TΔS",
        [(r"\Delta G", "ΔG", "change in free energy"), (r"\Delta H", "ΔH", "change in enthalpy"),
         ("T", "T", "temperature (K)"), (r"\Delta S", "ΔS", "change in entropy")],
        [r"gibbs(?:[- ]helmholtz)? (?:free energy )?(?:equation|relation)", r"gibbs free energy"], search="spontaneity"),
    # ---- chemistry ----------------------------------------------------------------------------------------------
    _eq("nernst", "Nernst equation", r"E = E^{\circ} - \dfrac{R T}{n F}\ln Q", "E = E° − (RT/nF) ln Q",
        [("E", "E", "cell potential"), (r"E^{\circ}", "E°", "standard cell potential"), ("n", "n", "electrons transferred"),
         ("Q", "Q", "reaction quotient")],
        [r"nernst" + _POSS + r" equation"], search="electrochemistry cell potential"),
    _eq("arrhenius", "Arrhenius equation", r"k = A\,e^{-E_{a}/R T}", "k = A e^(−Ea/RT)",
        [("k", "k", "rate constant"), ("A", "A", "pre-exponential factor"), (r"E_{a}", "Ea", "activation energy"),
         ("T", "T", "temperature (K)")],
        [r"arrhenius" + _POSS + r" equation"], search="rate constant activation energy"),
    _eq("henderson", "Henderson–Hasselbalch equation",
        r"\mathrm{pH} = \mathrm{p}K_{a} + \log \dfrac{[\mathrm{A^{-}}]}{[\mathrm{HA}]}", "pH = pKa + log([A⁻]/[HA])",
        [(r"\mathrm{p}K_{a}", "pKa", "acid dissociation constant (−log)"), (r"[\mathrm{A^{-}}]", "[A⁻]", "conjugate base"),
         (r"[\mathrm{HA}]", "[HA]", "weak acid")],
        [r"henderson(?:[- ]hasselbalch)?" + _POSS + r" equation"], search="buffer ph"),
    _eq("beer_lambert", "Beer–Lambert law", r"A = \varepsilon\, l\, c", "A = εlc",
        [("A", "A", "absorbance"), (r"\varepsilon", "ε", "molar absorptivity"), ("l", "l", "path length"), ("c", "c", "concentration")],
        [r"beer" + _POSS + r"(?:[- ]lambert)? law"], search="absorbance"),
    # ---- optics --------------------------------------------------------------------------------------------------
    _eq("snell", "Snell's law", r"n_{1}\sin\theta_{1} = n_{2}\sin\theta_{2}", "n₁ sin θ₁ = n₂ sin θ₂",
        [(r"n_{1}, n_{2}", "n₁, n₂", "refractive indices"), (r"\theta_{1}, \theta_{2}", "θ₁, θ₂", "angles of incidence and refraction")],
        [r"snell" + _POSS + r" law"], search="refraction"),
    _eq("lens", "Lens formula", r"\dfrac{1}{f} = \dfrac{1}{v} - \dfrac{1}{u}", "1/f = 1/v − 1/u",
        [("f", "f", "focal length"), ("v", "v", "image distance"), ("u", "u", "object distance")],
        [r"lens (?:formula|equation)"], search="optics"),
    _eq("mirror", "Mirror formula", r"\dfrac{1}{f} = \dfrac{1}{v} + \dfrac{1}{u}", "1/f = 1/v + 1/u",
        [("f", "f", "focal length"), ("v", "v", "image distance"), ("u", "u", "object distance")],
        [r"mirror (?:formula|equation)"], search="optics"),
    # ---- mathematics -------------------------------------------------------------------------------------------
    _eq("pythagoras", "Pythagoras theorem", r"a^{2} + b^{2} = c^{2}", "a² + b² = c²",
        [("a, b", "a, b", "legs of a right triangle"), ("c", "c", "hypotenuse")],
        [r"pythagoras" + _POSS + r" theorem", r"pythagorean theorem"], search="right triangle"),
    _eq("quadratic", "Quadratic formula", r"x = \dfrac{-b \pm \sqrt{b^{2} - 4ac}}{2a}", "x = (−b ± √(b² − 4ac))/2a",
        [("a, b, c", "a, b, c", "coefficients of ax² + bx + c = 0")],
        [r"quadratic formula", r"(?:sridharacharya|shreedharacharya)" + _POSS + r" formula"], search="roots"),
    _eq("euler_formula", "Euler's formula", r"e^{i\theta} = \cos\theta + i\sin\theta", "e^(iθ) = cos θ + i sin θ",
        [(r"\theta", "θ", "angle"), ("i", "i", "imaginary unit")], [r"euler" + _POSS + r" formula"], search="complex"),
    _eq("euler_identity", "Euler's identity", r"e^{i\pi} + 1 = 0", "e^(iπ) + 1 = 0", [],
        [r"euler" + _POSS + r" identity"], search="complex"),
    _eq("bayes", "Bayes' theorem", r"P(A \mid B) = \dfrac{P(B \mid A)\,P(A)}{P(B)}", "P(A|B) = P(B|A) P(A) / P(B)",
        [(r"P(A \mid B)", "P(A|B)", "probability of A given B")], [r"bayes" + _POSS + r" (?:theorem|rule|formula)"],
        search="probability conditional"),
    # ---- economics ----------------------------------------------------------------------------------------------
    _eq("gdp", "GDP (expenditure approach)", r"\mathrm{GDP} = C + I + G + (X - M)", "GDP = C + I + G + (X − M)",
        [("C", "C", "consumption"), ("I", "I", "investment"), ("G", "G", "government spending"), ("X - M", "X − M", "net exports")],
        [r"expenditure approach(?: to gdp)?", r"gdp (?:formula|equation)"], search="economics national income"),
)

BY_ID = {e.id: e for e in LIBRARY}

# a family named as a whole: its default members (the specific forms named in the same line win)
FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"maxwell" + _POSS + r" (?:four )?equations?(?! in integral form)", ("gauss_e", "gauss_b", "faraday", "ampere")),
    (_SCHRO + r"(?: wave)? equation", ("schrodinger_td",)),
    (r"(?:three )?equations of motion|kinematic equations", ("motion_1", "motion_2", "motion_3")),
)

# "let us write the equation", "this is its formula": the equation of what the slide is about
_SHOW = re.compile(r"\b(?:write|show|see|look at|derive|state|recall|here is)\b[^.?!]{0,30}\b(?:the|its|this|that)\s+"
                   r"(?:equation|formula|expression)s?\b")


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = t.replace("’", "'").replace("`", "'")
    return " ".join(re.sub(r"[^a-z0-9' -]+", " ", t).split())


def named(text: str, context: str = "") -> list[str]:
    """Library ids a transcript line names, in order. context: the unit's other lines / the slide title (for
    entries whose name is ambiguous, e.g. the continuity equation)."""
    t = normalise(text)
    ctx = normalise(f"{text} {context}")
    hits: list[tuple[int, str]] = []
    for e in LIBRARY:
        for a in e.aliases:
            m = re.search(rf"\b(?:{a})", t)
            if m and (not e.context or re.search(e.context, ctx)):
                hits.append((m.start(), e.id))
                break
    families = {BY_ID[i].family for _, i in hits if BY_ID[i].family}
    for rx, ids in FAMILIES:
        m = re.search(rf"\b(?:{rx})", t)
        if m and BY_ID[ids[0]].family not in families:
            hits += [(m.start() + k / 10, i) for k, i in enumerate(ids)]
    out: list[str] = []
    for _, i in sorted(hits):
        if i not in out:
            out.append(i)
    return out


def asked_for(text: str, subject: str) -> list[str]:
    """"Let us write the equation" while the slide is about a named equation ("Schrödinger Equation")."""
    if not _SHOW.search(normalise(text)):
        return []
    return named(subject)


def search(query: str, limit: int = 8) -> list[Equation]:
    """/control "Show equation": entries whose name, aliases or search words contain every query word."""
    words = normalise(query).split()
    if not words:
        return list(LIBRARY[:limit])
    out = []
    for e in LIBRARY:
        hay = normalise(f"{e.name} {e.search} {e.plain} {e.id.replace('_', ' ')}")
        if all(w in hay for w in words):
            out.append(e)
    return out[:limit]


def entry(eq_id: str) -> Optional[Equation]:
    return BY_ID.get(eq_id)


def piece(e: Equation, lines: tuple[int, ...] = ()):
    """The equation as a content piece for the composer (its own KaTeX and symbol legend)."""
    from copilot.presentation.content import FormulaData, Piece

    return Piece("formula", lines=lines, formula=FormulaData(
        e.plain, tuple((text, meaning) for _, text, meaning in e.legend), latex=e.latex, name=e.name, standard=True,
        var_latex=tuple(lx for lx, _, _ in e.legend)))
