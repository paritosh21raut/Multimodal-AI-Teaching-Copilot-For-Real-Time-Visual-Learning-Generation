"""The Bohr model of the atom (F-014 S3). Renderer: web/sims/bohr_atom.js.

Electrons in shells round the nucleus, filled 2, 8, 8 and the rest in the fourth (the class 9 rule, true up to Z = 20:
K 2, L 8, M 8, N 1-2; user 2026-10-19). The atom is the one said: by name ("sodium") or by atomic number ("atomic
number 11"). Before that the picture is the nucleus and empty shells: no electron count is drawn that nobody said.
Not drawn, with a notice on /control: Z > 20 (the 2, 8, 8 rule stops there), an ion (the picture is a neutral atom),
orbitals / subshells / "1s2" (another model).

An electron jump, when said ("an electron jumps from the third level to the second", "from n = 3 to n = 2"): the
outer electron moves between the two shells, a photon leaves (down) or comes in (up). Its energy and wavelength are
printed only for hydrogen (the Bohr energies E_n = -13.6 eV / n² hold only there):
    ΔE = 13.6 eV x |1/n_low² - 1/n_high²|,   λ = hc / ΔE = 1239.84 eV nm / ΔE
    3 -> 2: ΔE = 13.6 x (1/4 - 1/9) = 1.89 eV, λ = 656 nm (the red H-alpha line)

Steps: the nucleus, the electrons in shells, (when said) the electron absorbs energy and jumps up, it falls back and
emits a photon.
"""
from __future__ import annotations

import re
from typing import Any, Optional, Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, Part, SimBase, SimLabel, Slot, Solution, StepDef, Template, _Model, fmt, known,
)

RYDBERG_EV = 13.6
HC_EV_NM = 1239.84
MAX_Z = 20
MAX_N = 7

# Z 1-20: drawn; 21-30 and the common heavier ones: named only to say they are not drawn (a notice)
ELEMENTS_Z = {
    "hydrogen": 1, "helium": 2, "lithium": 3, "beryllium": 4, "boron": 5, "carbon": 6, "nitrogen": 7, "oxygen": 8,
    "fluorine": 9, "neon": 10, "sodium": 11, "magnesium": 12, "aluminium": 13, "aluminum": 13, "silicon": 14,
    "phosphorus": 15, "sulphur": 16, "sulfur": 16, "chlorine": 17, "argon": 18, "potassium": 19, "calcium": 20,
    "scandium": 21, "titanium": 22, "vanadium": 23, "chromium": 24, "manganese": 25, "iron": 26, "cobalt": 27,
    "nickel": 28, "copper": 29, "zinc": 30, "bromine": 35, "krypton": 36, "silver": 47, "tin": 50, "iodine": 53,
    "xenon": 54, "platinum": 78, "gold": 79, "mercury": 80, "lead": 82, "uranium": 92,
}
NAME_OF = {}
for _n, _z in ELEMENTS_Z.items():
    NAME_OF.setdefault(_z, _n.capitalize())
_ELEMENT = re.compile(r"\b(" + "|".join(sorted(ELEMENTS_Z, key=len, reverse=True)) + r")\b(?!\s+(?:\w+(?:ide|ate|ite)\b|"
                      r"gas|molecules?|compounds?|bonds?|rods?|cans?|nails?|filings|foil|wires?|us|to))", re.IGNORECASE)
# a name not drawn (Z > 20: iron, lead, tin are everyday words too) gives its notice only with an atom word in the line
_ATOM_CTX = re.compile(r"\b(?:atoms?|atomic|elements?|electrons?|shells?|protons?)\b", re.IGNORECASE)
_TAKE = re.compile(r"\b(?:take|consider|about)\s+(?:an? |the )?(?:atom of )?$", re.IGNORECASE)  # "now consider iron"
_ION = re.compile(r"^\s*(?:ions?\b|\+|−|-\s?ion)", re.IGNORECASE)
# an ion by its symbol: "Na plus ion", "Cl minus", "Mg 2+" (then the name said is not read as the atom)
_ION_SYMBOL = re.compile(r"\b(?-i:[A-Z][a-z]?)\s?(?:\d\s?)?(?:\+|−|\bplus\b|\bminus\b)(?:\s?ions?\b)?(?!\s?\d)",
                         re.IGNORECASE)
_ORBITALS = re.compile(r"\borbitals?\b|\bsub-?shells?\b|\b[1-7]\s?[spdf]\s?(?:\d|two|one|six|ten)\b|\bquantum numbers?\b"
                       r"|\b[spdf][- ]orbitals?\b|\baufbau\b|\bhund'?s rule\b", re.IGNORECASE)
_ORD = {"first": 1, "one": 1, "1": 1, "second": 2, "two": 2, "2": 2, "third": 3, "three": 3, "3": 3, "fourth": 4,
        "four": 4, "4": 4, "fifth": 5, "five": 5, "5": 5, "sixth": 6, "six": 6, "6": 6, "seventh": 7, "seven": 7,
        "7": 7, "ground": 1, "k": 1, "l": 2, "m": 3, "n": 4}
_LEVEL = r"(?:(?:the\s+)?(?:(?:energy\s+)?(?:level|shell|orbit|state)\s+)?(?:n\s*(?:=|equals?|is)\s*)?(?P<{g}>first|second|third|fourth|fifth|sixth|seventh|one|two|three|four|five|six|seven|[1-7]|ground|[klmn](?=[- ]shell))(?:\s*(?:st|nd|rd|th))?(?:\s+(?:energy\s+)?(?:level|shell|orbit|state))?)"
_JUMP = re.compile(r"\bfrom\s+" + _LEVEL.format(g="a") + r"\s+(?:energy\s+level\s+|shell\s+|orbit\s+|state\s+)?"
                   r"(?:to|into|down to|up to)\s+" + _LEVEL.format(g="b") + r"(?!\w|\.\d)", re.IGNORECASE)
# a jump needs a level word or "n =" inside "from .. to ..", or an electron and a jump verb in the line: "the number of
# shells goes from 2 to 3" is not one (review)
_JUMP_NOUN = re.compile(r"\b(?:level|shell|orbit|state|ground)\b|\bn\s*(?:=|equals?\b|is\b)|\b[klmn][- ]shell", re.IGNORECASE)
_JUMP_CTX = re.compile(r"\belectrons?\b[^.;]{0,60}\b(?:jump\w*|falls?|fell|drops?|moves?|goes|comes|returns?|"
                       r"transition\w*|excit\w*|de-?excit\w*|emits?|absorbs?)\b", re.IGNORECASE)

SLOTS = (
    Slot("z", "Atomic number", "Z", "", 1.0, float(MAX_Z), 1.0, 6.0, "count",
         names=r"atomic number|proton number|number of protons"),
    # an electron jump between two shells (0: none); read only by the template's own reading (parse)
    Slot("n_from", "Jump from shell", "n₁", "", 0.0, float(MAX_N), 1.0, 0.0, "level", absent=True),
    Slot("n_to", "Jump to shell", "n₂", "", 0.0, float(MAX_N), 1.0, 0.0, "level", absent=True),
)
STEPS = (
    StepDef("nucleus", "The nucleus: protons and neutrons",
            r"\bnucleus\b|\bprotons? and neutrons?\b|\bneutrons? and protons?\b"),
    StepDef("shells", "Electrons move in fixed shells",
            r"\belectrons? (?:\w+ ){0,3}(?:revolve|move|orbit|go round|are arranged|are filled|are distributed|occupy)\b"
            r"|\b(?:fixed|stationary|circular) (?:shells|orbits|paths|energy levels)\b|\b2,? 8,? 8\b"
            r"|\b(?:electronic configuration|electron(?:ic)? arrangement|arrangement of electrons)\b"),
    StepDef("absorb", "It absorbs energy and jumps up",
            r"\babsorbs? (?:energy|a photon|light|heat)\b|\b(?:gets|becomes|is) excited\b|\bexcited state\b"
            r"|\bjumps? (?:up )?to (?:a )?higher\b", optional=True, element="photon"),
    StepDef("emit", "It falls back and emits a photon",
            r"\bemits? (?:a )?(?:photon|light|energy|radiation)\b|\bde-?excit\w*|\bgives? (?:out|off) (?:a )?(?:photon|light)\b"
            # falling back / to a lower level names the step only for an electron or "it" (not "the light falls back")
            r"|\b(?:electrons?|it)\b[^.;]{0,40}?\b(?:falls? back|returns? to (?:a |the )?(?:lower|ground)|"
            r"jumps? (?:back )?(?:down )?to (?:a )?lower)\b",
            optional=True, element="photon"),
)
PARTS = (
    Part("nucleus", "Nucleus", r"\bnucleus\b"),
    Part("protons", "Protons", r"\bprotons?\b"),
    Part("neutrons", "Neutrons", r"\bneutrons?\b"),
    Part("electrons", "Electrons", r"\belectrons?\b"),
    Part("photon", "Photon", r"\bphotons?\b"),
    Part("k", "K", r"\bK[- ]shell\b|\bfirst (?:shell|orbit|energy level)\b"),
    Part("l", "L", r"\bL[- ]shell\b|\bsecond (?:shell|orbit|energy level)\b"),
    Part("m", "M", r"\bM[- ]shell\b|\bthird (?:shell|orbit|energy level)\b"),
    Part("n", "N", r"\bN[- ]shell\b|\bfourth (?:shell|orbit|energy level)\b"),
)
ELEMENTS = (
    Element("nucleus", "Nucleus"), Element("shells", "Shells"), Element("electrons", "Electrons"),
    Element("photon", "Photon"), Element("readout", "Values"),
)


class BohrParams(_Model):
    z: float = Field(default=6.0, ge=1.0, le=float(MAX_Z))
    n_from: float = Field(default=0.0, ge=0.0, le=float(MAX_N))
    n_to: float = Field(default=0.0, ge=0.0, le=float(MAX_N))


class BohrSim(SimBase):
    template: Literal["bohr_atom"] = "bohr_atom"
    params: BohrParams = Field(default_factory=BohrParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("element", "config", "nucleus", "protons", "neutrons", "electrons", "photon", "k", "l", "m", "n")


_SLOTS = {s.name: s for s in SLOTS}


def shells(z: int) -> list[int]:
    """Electrons per shell, the 2, 8, 8 rule (Z <= 20): 11 -> [2, 8, 1], 20 -> [2, 8, 8, 2]."""
    out, left = [], z
    for cap in (2, 8, 8, 2):
        if left <= 0:
            break
        out.append(min(cap, left))
        left -= cap
    return out


def solve(p: BohrParams, src: dict[str, str]) -> Solution:
    z_ok = src.get("z") in ("said", "teacher", "computed")
    z = int(round(p.z))
    occ = shells(z) if z_ok else []
    n1, n2 = int(round(p.n_from)), int(round(p.n_to))
    jump = n1 >= 1 and n2 >= 1 and n1 != n2 and known(src, _SLOTS, "n_from", "n_to") and \
        src.get("n_from") in ("said", "teacher") and src.get("n_to") in ("said", "teacher")
    full = jump and z_ok and min(n1, n2) < len(occ)  # into / out of a full inner shell (sodium "5 to 2"): not drawn
    if full:
        jump = False
    drive: dict[str, float] = {"z": float(z) if z_ok else 0.0, "shells": float(max([len(occ) if z_ok else 4] + ([n1, n2] if jump else [])))}  # 4 empty shells: no atom said
    for i, k in enumerate(occ):
        drive[f"e{i + 1}"] = float(k)
    labels: dict[str, SimLabel] = {}
    derived: list[Derived] = []
    if z_ok:
        labels["element"] = SimLabel(symbol=NAME_OF[z], text=f"Z = {z}", source="said" if src["z"] != "computed" else "computed")
        derived.append(Derived(id="config", label="Electrons per shell", symbol="K, L, M, N"[:3 * len(occ) - 2],
                               value=float(z), text=", ".join(str(k) for k in occ)))
        derived.append(Derived(id="valence", label="Valence electrons", symbol="Valence electrons", value=float(occ[-1]),
                               text=str(occ[-1])))
    if full:
        derived.append(Derived(id="jump_note", label="Jump", symbol="Jump", value=0.0,
                               text=f"not drawn: shell {min(n1, n2)} of {NAME_OF[z]} is full (an outer electron jumps)"))
    if jump:
        drive.update(n_from=float(n1), n_to=float(n2), emits=1.0 if n2 < n1 else 0.0)
        if z_ok and z == 1:  # the Bohr energies hold for hydrogen only
            lo, hi = min(n1, n2), max(n1, n2)
            dE = RYDBERG_EV * (1 / lo ** 2 - 1 / hi ** 2)
            lam = HC_EV_NM / dE
            drive["lambda_nm"] = lam
            derived.append(Derived(id="dE", label="Photon energy", symbol="ΔE", value=dE, unit="eV", text=f"{fmt(dE)} eV"))
            derived.append(Derived(id="lambda", label="Wavelength", symbol="λ", value=lam, unit="nm", text=f"{fmt(lam)} nm"))
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: BohrParams, src: dict[str, str]) -> list[str]:
    return ["nucleus", "shells", "electrons", "readout"]


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    """The atom by name, an electron jump, and the notices (an ion, Z > 20, orbitals): ("!", text, said, pos)."""
    out: list[tuple[str, Any, str, int]] = []
    m = _ORBITALS.search(line)
    if m:
        out.append(("!", "Orbitals and subshells are not drawn: this is the Bohr model (shells 2, 8, 8)", m.group(0),
                    m.start()))
    for e in _ELEMENT.finditer(line):
        if ELEMENTS_Z[e.group(1).lower()] > MAX_Z and not _ATOM_CTX.search(line) and \
                not _TAKE.search(line[:e.start()]):
            continue  # "the iron rod", "lead us to": not an atom
        if _ION.match(line[e.end():]) or _ION_SYMBOL.search(line):
            out.append(("!", f"Heard “{e.group(0)} ion” - not drawn: the picture is a neutral atom", e.group(0), e.start()))
            continue
        out.append(("z", float(ELEMENTS_Z[e.group(1).lower()]), e.group(0), e.start()))
        break  # the first element said is the atom
    j = _JUMP.search(line)
    if j and (_JUMP_NOUN.search(j.group(0)) or _JUMP_CTX.search(line)):
        a, b = _ORD[j.group("a").lower()], _ORD[j.group("b").lower()]
        if a != b:
            out.append(("n_from", float(a), j.group(0), j.start("a")))
            out.append(("n_to", float(b), j.group(0), j.start("b")))
    return out


_STEP_WORDS = "|".join(d.words for d in STEPS)

TEMPLATE = Template(
    id="bohr_atom", name="The Bohr model of the atom", subject="chemistry",
    sim=BohrSim, params=BohrParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    # Bohr's model by name, or the shells: Rutherford's "electrons revolve in circular orbits" is not this (test4)
    setup=re.compile(r"\bbohr'?s? (?:model|atom|atomic model|theory)\b|\bbohr model\b"
                     r"|\b(?:electronic configuration|electron(?:ic)? arrangement|arrangement of electrons|"
                     r"distribution of electrons) (?:of|in) (?:an? |the )?(?:\w+ )?(?:atoms?|element|" +
                     "|".join(n for n, z in ELEMENTS_Z.items() if z <= MAX_Z) + r")\b"
                     r"|\belectrons? (?:are )?(?:arranged|distributed|filled) in (?:shells|energy levels)\b"
                     r"|\bK,? L,? M,? (?:and )?N shells?\b|\bshells? of (?:an? |the )?atom\b", re.IGNORECASE),
    lexicon=re.compile(rf"{_STEP_WORDS}|\b(?:atoms?|atomic|electrons?|shells?|orbits?|nucleus|protons?|neutrons?|"
                       rf"energy levels?|photons?|excited|ground state|orbitals?|sub-?shells?|ions?)\b|{_ELEMENT.pattern}",
                       re.IGNORECASE),
    # programming / everyday "atom" and "shell"; orbitals (another model: S0 negative)
    guard=re.compile(r"\batomic (?:operations?|commits?|transactions?|variables?|habits?|bombs?)\b|\batom editor\b"
                     r"|\bshell (?:scripts?|commands?|prompt)\b|\b(?:bash|c|z|unix|linux) shell\b|\bnuclear shell model\b"
                     r"|\borbitals?\b|\bsub-?shells?\b|\bquantum numbers?\b", re.IGNORECASE),
    aliases=("atom", "bohr", "shells", "electron configuration", "energy levels", "electrons"),
    steps=STEPS, parts=PARTS, parse=parse, listens=_ELEMENT.pattern + "|" + _ORBITALS.pattern,
)
