"""Plain-text formula → LaTeX for KaTeX (F-007a). Pure and deterministic; no LLM.

The model writes formulas as plain text ("6CO2 + 6H2O → C6H12O6 + 6O2", "I1 = (R2 / (R1 + R2)) * I_total",
"KE = 1/2 mv²", "carbon dioxide plus water, in the presence of sunlight, gives glucose plus oxygen"). A small
recursive-descent parser builds LaTeX: stacked fractions (brackets around a numerator/denominator dropped), roots,
powers, ±, R1 → R₁ and I_total → I_total subscripts, implicit products (2a, 4ac, I²R), chemical formulas and ions.
Words and chemical formulas become ``\\text{}`` (the display styles it with the slide font); symbols and words are
decided per side of = / → ("Kinetic energy = 1/2 m v^2"). ``to_latex`` returns "" when it cannot build a safe
expression; the display then shows the formula as written.

``mark_math`` finds equations inside ordinary slide text ("has the form ax² + bx + c = 0", "H⁺ + OH⁻ → H₂O") and
returns the text with ``\\(…\\)`` around them, so points, examples and definitions show real formulas too.
"""
from __future__ import annotations

import re
from typing import Optional

ELEMENTS = frozenset("""H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se
Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W
Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr""".split())
# single-element molecules written with a count (O2, O3, S8, P4); anything else alone (B12, N95, U2) is not chemistry
_ELEMENTAL = frozenset("H N O F Cl Br I S P".split())

_CHEM = re.compile(r"^(?P<coef>\d*)(?P<body>(?:[A-Z][a-z]?\d*)+)$")
_PART = re.compile(r"([A-Z][a-z]?)(\d*)")
_ION = re.compile(r"^(?P<coef>\d*)(?P<body>(?:[A-Z][a-z]?[0-9₀-₉]*)+)(?P<charge>[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻])$")

GREEK = {name: "\\" + name for name in (
    "alpha beta gamma epsilon theta lambda mu pi rho sigma tau phi omega "
    "Gamma Delta Theta Lambda Pi Sigma Phi Omega").split()}
GREEK.update({"delta": r"\Delta", "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\epsilon",
              "θ": r"\theta", "λ": r"\lambda", "μ": r"\mu", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau",
              "φ": r"\phi", "ω": r"\omega", "Δ": r"\Delta", "Σ": r"\Sigma", "Ω": r"\Omega"})
# capital + these letters is a subscripted quantity in a formula (Vin → V_in, Req → R_eq)
_SUB_TAILS = {"in", "out", "eq", "net", "max", "min", "avg", "tot", "total", "rms"}

_SUB_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")

# spoken operators → symbols (order matters: longer phrases first)
_PHRASES = [
    (r"\b([A-Z]) (?:equivalent)\b", r"\1_eq"), (r"\b([A-Z]) total\b", r"\1_total"),  # spoken "R equivalent"
    (r"\b(?:is equal to|equals to|equal to|equals)\b", "="), (r"\bgives us\b", "→"), (r"\bgives\b", "→"),
    (r"\bproduces\b", "→"), (r"\byields\b", "→"), (r"\bforms\b", "→"),
    (r"\bplus or minus\b|\bplus minus\b|\+/-|\+-", "±"), (r"\bplus\b", "+"), (r"\bminus\b", "−"),
    (r"\bsquare root of\b|\bunder root\b|\broot of\b", "√"),
    (r"(?<=\b[A-Za-z0-9]) into (?=[A-Za-z0-9]\b)", " × "),  # Indian English "m into a" = m × a (symbols only)
    (r"\bhalf\b(?= ?[A-Za-z])", "1/2 "), (r"\bmultiplied by\b", "×"), (r"\btimes\b", "×"),
    (r"\bsquared\b|\bsquare\b", "^2"), (r"\bcubed\b|\bcube\b", "^3"),
    (r"\bdivided by\b", "/"), (r"\bupon\b", "/"),
    (r"(?<=\b[A-Za-z0-9]) by (?=[A-Za-z0-9]{1,3}\b)", " / "),  # "w by q", "1 by r"
    (r"(?<=\^\d) by (?=[A-Za-z0-9]{1,3}\b)", " / "),  # "V squared by R"
]
# two-letter capitals that are names, not products (RC, IR, LC are products)
_NAMES = {"KE", "PE", "GPE", "EMF", "AC", "DC", "SI", "pH", "RMS"}
_ARROWS = re.compile(r"\s*(?:-+>|=+>|⟶|⇒|→)\s*")
_CONDITION = re.compile(r",?\s*\bin the presence of\b\s+(?P<c>[^,→=]+?)\s*,?\s*(?=→)", re.IGNORECASE)
_WORD_HYPHEN = re.compile(r"(?<=[A-Za-z])-(?=[a-z]{2})")
_LATEX_LIKE = re.compile(r"\\[A-Za-z]+|[_^]\{")
_UNSAFE = re.compile(r"\\(?:href|url|html\w*|includegraphics|def|gdef|newcommand|renewcommand|let)\b")
_TEXT_ESCAPE = str.maketrans({"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
                              "#": r"\#", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"})
_MAX_LEN = 300

_RELATIONS = {"=": "=", "≈": r"\approx", "≠": r"\neq", "≤": r"\leq", "≥": r"\geq", "<": "<", ">": ">",
              "∝": r"\propto", "→": r"\rightarrow", ",": r",\quad", "or": r"\quad\text{or}\quad",
              "and": r"\quad\text{and}\quad"}
_ADD = {"+": "+", "−": "-", "-": "-", "±": r"\pm"}
_MUL = {"×": r"\times", "*": r"\times", "·": r"\cdot", "÷": r"\div"}
_TOKEN = re.compile(r"\s*(?:(?P<ph>\x00\d+\x00)|(?P<cnum>\d+[A-Za-z]{1,3}(?![A-Za-z0-9_]))|(?P<num>\d+(?:\.\d+)?)|"
                    r"(?P<word>[A-Za-zΑ-Ωα-ω&][A-Za-zΑ-Ωα-ω0-9_'’‐&]*)|(?P<op>[=≈≠≤≥<>∝→,+\-−±×*·÷/^()√\[\]%]))")


class _Fail(Exception):
    pass


def chem_parts(token: str) -> list[tuple[str, str]] | None:
    """"C6H12O6" → [("C","6"),("H","12"),("O","6")] if the token is a chemical formula, else None.
    Needs a count somewhere, never a count of 1; a single element only for elemental molecules (O2, S8)."""
    m = _CHEM.match(token)
    if not m:
        return None
    parts = _PART.findall(m.group("body"))
    if any(sym not in ELEMENTS for sym, _ in parts):
        return None
    counts = [n for _, n in parts if n]
    if not counts or any(n == "1" or n.startswith("0") for n in counts):
        return None
    if len(parts) == 1 and (parts[0][0] not in _ELEMENTAL or not 2 <= int(parts[0][1]) <= 8):
        return None
    return parts


def _text(s: str) -> str:
    return r"\text{" + s.translate(_TEXT_ESCAPE) + "}"


def _chem_body(parts: list[tuple[str, str]]) -> str:
    body, run = "", ""
    for sym, n in parts:  # one text run until a count: "CO2" → \text{CO}_{\text{2}}
        run += sym
        if n:
            body += _text(run) + "_{" + _text(n) + "}"
            run = ""
    return body + (_text(run) if run else "")


def _chem_latex(word: str, elemental: bool = True) -> Optional[str]:
    """'6CO2' → 6 CO₂, 'OH⁻' → OH⁻, 'Ca²⁺' → Ca²⁺: every part as text, so it is in the slide font."""
    m = _ION.match(word)
    if m:
        parts = _PART.findall(m.group("body").translate(_SUB_DIGITS))
        if all(sym in ELEMENTS for sym, _ in parts):
            charge = m.group("charge").translate(_SUP_DIGITS)
            coef = m.group("coef")
            return (_text(coef) + r"\," if coef else "") + _chem_body(parts) + "^{" + charge + "}"
    w = word.translate(_SUB_DIGITS)
    parts = chem_parts(w)
    if parts is None or (not elemental and len(parts) == 1):
        return None
    coef = _CHEM.match(w).group("coef")  # type: ignore[union-attr]
    return (_text(coef) + r"\," if coef else "") + _chem_body(parts)


_UPON = re.compile(r"\b(?:upon|divided by)\b(?P<den>.+?)(?=\b(?:times|into|multiplied by|equals?|is equal to|or|and)\b"
                   r"|[=,×*]|$)", re.IGNORECASE)


def _group_spoken_denominators(s: str) -> str:
    """Spoken "R2 upon R1 plus R2 times Vin" means R2 / (R1 + R2) × Vin: the denominator runs to the next
    times / equals / end. Grouped only when it holds a spoken plus or minus."""
    def group(m: re.Match) -> str:
        den = m.group("den").strip()
        if re.search(r"\b(?:plus|minus)\b|[+−-]", den) and not den.startswith("("):
            return f"upon ({den}) "
        return m.group(0)
    return _UPON.sub(group, s)


def _normalise(expr: str) -> tuple[str, str, list[str]]:
    """Spoken words → symbols, chemical formulas → placeholders, condition over the arrow split off."""
    s = " ".join(expr.replace("\u2212", "−").split()).rstrip(". ")
    label, colon, rest = s.partition(":")
    if colon and ("=" in rest or "→" in rest) and "=" not in label and len(label.split()) <= 4:
        s = rest.strip()  # "Ohm's law: V = IR" → the formula; the slide title names it
    chem: list[str] = []
    # R1, V2 in the formula: "I2" is a current there, not iodine
    elemental = not any(re.fullmatch(r"[A-Za-z]\d+", w) and chem_parts(w) is None for w in re.findall(r"\w+", s))

    def keep_chem(m: re.Match) -> str:
        latex = _chem_latex(m.group(0), elemental)
        if latex is None:
            return m.group(0)
        chem.append(latex)
        return f" \x00{len(chem) - 1}\x00 "
    s = re.sub(r"(?<![\w^])\d*(?:[A-Z][a-z]?[0-9₀-₉]*)+[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]?(?![\w])", keep_chem, s)
    s = s.translate(_SUB_DIGITS)
    s = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: "^" + m.group(1).translate(_SUP_DIGITS) + " ", s)
    s = s.replace("½", " 1/2 ").replace("√", " √ ")
    s = _group_spoken_denominators(s)
    s = _WORD_HYPHEN.sub("\u2010", s)  # "x-ray", "carbon-dioxide": a hyphen inside a word is not a minus
    for pat, rep in _PHRASES:
        s = " ".join(re.sub(pat, f" {rep} ", s, flags=re.IGNORECASE).split())
        s = re.sub(r"\^ (\d)", r"^\1", s)
    s = _ARROWS.sub(" → ", s)
    s = " ".join(s.split())
    condition = ""
    m = _CONDITION.search(s)
    if m:
        condition = m.group("c").strip()
        s = (s[: m.start()] + " " + s[m.end():]).strip()
    return s, condition, chem


def _tokens(s: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    s = s.rstrip()
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise _Fail(f"cannot read {s[pos:pos + 10]!r}")
        pos = m.end()
        kind = m.lastgroup or "op"
        val = m.group(kind)
        if kind == "word" and val.lower() in ("or", "and"):
            kind, val = "op", val.lower()
        out.append((kind, val))
    return out


def _short(w: str) -> bool:
    return (len(w) <= 3 or w in GREEK or bool(re.fullmatch(r"[A-Za-z]\d+|[A-Za-z]_[A-Za-z0-9]+", w))
            or (w[:1].isupper() and w[1:] in _SUB_TAILS))


def _symbolic_sides(toks: list[tuple[str, str]]) -> list[bool]:
    sides: list[list[tuple[str, str]]] = [[]]
    for k, v in toks:
        if k == "op" and v in _RELATIONS:
            sides.append([])
        else:
            sides[-1].append((k, v))
    flags = []
    for side in sides:
        words = [v for k, v in side if k == "word"]
        has_number = any(k == "num" for k, _ in side)
        singles = [w for w in words if len(w) == 1 or w in GREEK or re.fullmatch(r"[A-Za-z]\d+|[A-Za-z]_\w+", w)
                   or (has_number and re.fullmatch(r"[a-z]{2,3}", w))]
        flags.append(bool(singles) and all(_short(w) for w in words))
    if any(flags):  # "F = ma": a side of short letter groups next to a symbolic side is symbolic too
        flags = [f or all(_short(v) for k, v in side if k == "word") for f, side in zip(flags, sides)]
    return flags


_GROUP = re.compile(r"^\\left\((?P<inner>.*)\\right\)$")


def _bare(latex: str) -> str:
    """Brackets around a whole numerator or denominator are not shown: the fraction bar groups it."""
    m = _GROUP.match(latex)
    return m.group("inner") if m and _balanced(m.group("inner")) else latex


class _Parser:
    def __init__(self, toks: list[tuple[str, str]], chem: list[str], condition: str) -> None:
        self.t, self.i, self.chem, self.condition = toks, 0, chem, condition
        self.symbolic = _symbolic_sides(toks)
        self.side = 0
        self.depth = 0

    def peek(self) -> tuple[str, str]:
        return self.t[self.i] if self.i < len(self.t) else ("end", "")

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self) -> str:
        out = self.relation()
        if self.i != len(self.t):
            raise _Fail(f"unexpected {self.peek()[1]!r}")
        return out

    def relation(self) -> str:
        parts = [self.additive()]
        while self.peek()[0] == "op" and self.peek()[1] in _RELATIONS:
            op = self.take()[1]
            if op == "→" and self.condition:
                parts.append(r"\xrightarrow{" + _text(self.condition) + "}")
                self.condition = ""
            else:
                parts.append(_RELATIONS[op])
            self.side += 1
            parts.append(self.additive())
        return " ".join(parts)

    def additive(self) -> str:
        parts = []
        if self.peek() in (("op", "+"), ("op", "−"), ("op", "-"), ("op", "±")):
            parts.append(_ADD[self.take()[1]])
        parts.append(self.product())
        while self.peek()[0] == "op" and self.peek()[1] in _ADD:
            parts.append(_ADD[self.take()[1]])
            parts.append(self.product())
        return " ".join(parts)

    def _starts_atom(self) -> bool:
        k, v = self.peek()
        return k in ("num", "cnum", "word", "ph") or (k == "op" and v in ("(", "[", "√", "%"))

    def product(self) -> str:
        """Factors joined by ×, ·, ÷ or by nothing (implicit). A "/" divides the implicit product before it by the
        factor after it: "R1 R2 / (R1 + R2)" → R1R2 over R1 + R2, "m v^2 / 2", "1/2 m v^2" → ½ m v²."""
        out: list[str] = []
        run = [self.power()]
        while True:
            k, v = self.peek()
            if (k, v) == ("op", "/"):
                self.take()
                self.depth += 1
                den = self.power()
                self.depth -= 1
                cmd = r"\dfrac" if self.depth == 0 else r"\frac"
                run = [cmd + "{" + _bare(" ".join(run)) + "}{" + _bare(den) + "}"]
            elif k == "op" and v in _MUL:
                self.take()
                out += [" ".join(run), _MUL[v]]
                run = [self.power()]
            elif self._starts_atom():
                run.append(self.power())
            else:
                out.append(" ".join(run))
                return " ".join(out)

    def power(self) -> str:
        base = self.atom()
        while self.peek() == ("op", "^"):
            self.take()
            sign = ""
            if self.peek() in (("op", "−"), ("op", "-")):
                self.take()
                sign = "-"
            k, v = self.peek()
            if k == "op" and v in ("+", "−", "-") or k == "end":
                raise _Fail("bad exponent")
            exp = self.atom(single=True)
            base = base + "^{" + sign + _bare(exp) + "}"
        return base

    def atom(self, single: bool = False) -> str:
        k, v = self.take()
        if k == "ph":
            return self.chem[int(v.strip("\x00"))]
        if k == "num":
            return v
        if k == "cnum":  # "2a", "4ac": one compact product, so "/ 2a" divides by 2a
            n = re.match(r"\d+", v).group(0)  # type: ignore[union-attr]
            return n + " " + " ".join(v[len(n):])
        if k == "op" and v in ("(", "["):
            inner = self.relation()
            if self.take() != ("op", ")" if v == "(" else "]"):
                raise _Fail("unbalanced brackets")
            if re.fullmatch(r"\\dfrac\{.*\}|\\frac\{.*\}", inner) and _balanced(inner):
                return inner  # "(R2 / (R1 + R2)) × I": the fraction bar is the grouping
            return r"\left(" + inner + r"\right)"
        if k == "op" and v == "√":
            if self.peek() == ("op", "("):
                return r"\sqrt{" + _bare(self.atom()) + "}"
            return r"\sqrt{" + self.power() + "}"
        if k == "word":
            return self.word(v, single)
        if k == "op" and v == "%":
            return r"\%"
        raise _Fail(f"unexpected {v!r}")

    def word(self, w: str, single: bool) -> str:
        symbolic = self.symbolic[min(self.side, len(self.symbolic) - 1)]
        if w in GREEK:
            return GREEK[w]
        if len(w) > 1 and w[0] in GREEK and re.fullmatch(r"[A-Za-z]\w{0,2}", w[1:]):
            return GREEK[w[0]] + " " + self.word(w[1:], True)  # "Δx", "ΔU"
        if not symbolic:
            words = [w]
            while not single and self.peek()[0] == "word" and self.peek()[1] not in GREEK:
                words.append(self.take()[1])
            return _text(" ".join(words))
        if len(w) == 1:
            return w
        m = re.fullmatch(r"([A-Za-z])(\d+)", w)
        if m:
            return f"{m.group(1)}_{{{m.group(2)}}}"
        m = re.fullmatch(r"([A-Za-z])_([A-Za-z0-9]+)", w)
        if m:
            sub = m.group(2)
            return f"{m.group(1)}_{{{sub if len(sub) == 1 or sub.isdigit() else _text(sub)}}}"
        if w[:1].isupper() and w[1:] in _SUB_TAILS:
            return f"{w[0]}_{{{_text(w[1:])}}}"
        if re.fullmatch(r"[a-z]{2,3}", w) or (re.fullmatch(r"[A-Z]{2}", w) and w not in _NAMES):
            return " ".join(w)  # "mv", "ac", "mgh", "RC", "IR": a product of variables
        return _text(w)  # "KE", "PE": a name, upright


def to_latex(expr: str) -> str:
    """Plain formula text → KaTeX LaTeX, or "" when no safe expression can be built."""
    expr = _DASHES.sub("-", (expr or "").strip())
    if not expr or len(expr) > _MAX_LEN:
        return ""
    if _LATEX_LIKE.search(expr):
        return expr if _balanced(expr) and not _UNSAFE.search(expr) else ""
    try:
        s, condition, chem = _normalise(expr)
        toks = _tokens(s)
        if not toks:
            return ""
        latex = _Parser(toks, chem, condition).parse()
    except (_Fail, IndexError, ValueError):
        return ""
    return latex if latex and _balanced(latex) else ""


def _balanced(s: str) -> bool:
    depth = 0
    escaped = False
    for ch in s:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def visible_length(latex: str) -> int:
    """Rough count of characters KaTeX will show (height model)."""
    s = re.sub(r"\\(?:text|mathrm)\{([^}]*)\}", r"\1", latex)
    s = re.sub(r"\\(?:dfrac|frac)\{([^}]*)\}\{([^}]*)\}", lambda m: max(m.group(1), m.group(2), key=len), s)
    s = re.sub(r"\\[A-Za-z]+", "x", s)
    return len(re.sub(r"[{}_^\s,;]", "", s)) + s.count(" ") // 3


def has_fraction(latex: str) -> bool:
    return "\\frac" in latex or "\\dfrac" in latex


# ---- equations inside slide text ------------------------------------------------------------------------------

_RELATION_CHARS = re.compile(r"=|→|->|⟶|≈|≤|≥")
_OP_WORDS = {"+", "−", "-", "=", "→", "->", "×", "÷", "±", "/", "≈", "≤", "≥", "·"}
_MATHY = re.compile(r"[=→^²³√±⁺⁻₀-₉×÷·]|^\d+[a-z]{1,2}$")
_UNIT = re.compile(r"^[a-zA-Zµ]{1,3}(?:/[a-zA-Zµ]{1,3})+[²³]?$")
_PUNCT_LEAD, _PUNCT_TRAIL = "(", "),;.:"
_SPOKEN_OPS = re.compile(r"\b(?:equals?|plus|minus|upon|times|into|squared|divided by|multiplied by|gives)\b",
                         re.IGNORECASE)
_SENTENCE_WORDS = re.compile(r"\b(?:is|are|was|were|the|of|in|which|that|when|while|using|because)\b", re.IGNORECASE)


def _whole_equation(text: str) -> Optional[str]:
    """The whole item is an equation ("H⁺ + OH⁻ → H₂O", "Mechanical energy = PE + KE"), maybe after a short label."""
    label, colon, rest = text.partition(":")
    prefix = ""
    if colon and len(label.split()) <= 3 and _RELATION_CHARS.search(rest):
        prefix, text = label.strip() + ": ", rest.strip()
    body = text.rstrip(".")
    shape = body
    if not _RELATION_CHARS.search(body):  # spoken: "V2 equals R2 upon R1 plus R2 times Vin" (a model point, live)
        for pat, rep in _PHRASES:
            shape = re.sub(pat, f" {rep} ", shape, flags=re.IGNORECASE)
        if not _RELATION_CHARS.search(shape) or len(_SPOKEN_OPS.findall(body)) < 2:
            return None
    if len(body.split()) > 16:
        return None
    operands = re.split(r"\s*(?:=|→|->|⟶|≈|≤|≥|\+|−|×|÷|/|\s-\s|±)\s*", shape)
    if any(len(o.split()) > 4 or _SENTENCE_WORDS.search(o) for o in operands):
        return None
    latex = to_latex(body)
    return prefix + r"\(" + latex + r"\)" if latex else None


def _word_core(w: str) -> tuple[str, str, str]:
    lead = len(w) - len(w.lstrip(_PUNCT_LEAD))
    trail = len(w) - len(w.rstrip(_PUNCT_TRAIL))
    return w[:lead], w[lead:len(w) - trail], w[len(w) - trail:]


_DASHES = re.compile(r"[‐‑‒–]")  # the model writes "x²‑5x+6=0" with U+2011 (live test)


def mark_math(text: str) -> str:
    """Slide text with ``\\(latex\\)`` around the equations in it, or "" when it holds none."""
    t = _DASHES.sub("-", " ".join((text or "").split()))
    if not t or "\\(" in t or len(t) > _MAX_LEN:
        return ""
    whole = _whole_equation(t)
    if whole:
        return whole
    words = t.split(" ")
    cores = [_word_core(w)[1] for w in words]

    def mathy(i: int) -> bool:
        c = cores[i]
        return bool(c) and not _UNIT.match(c) and (c in _OP_WORDS or bool(_MATHY.search(c)))

    def operand_near_op(i: int) -> bool:  # "bx", "c", "0" count when an operator is next to them
        c = cores[i]
        if not re.fullmatch(r"[A-Za-z]{1,2}\d?|\d+(?:\.\d+)?", c):
            return False
        return any(0 <= j < len(cores) and cores[j] in _OP_WORDS for j in (i - 1, i + 1))

    out, i, found = [], 0, False
    while i < len(words):
        if not (mathy(i) or operand_near_op(i)):
            out.append(words[i])
            i += 1
            continue
        j = i
        while j < len(words) and (mathy(j) or operand_near_op(j)):
            j += 1
        a, b = i, j  # drop operators at the ends ("formula → x=3": the arrow stays text)
        while a < b and cores[a] in _OP_WORDS:
            a += 1
        while b > a and cores[b - 1] in _OP_WORDS:
            b -= 1
        run = [cores[a]] if b - a == 1 else [words[k] for k in range(a, b)]
        if b - a >= 1:
            first_lead, _, _ = _word_core(words[a])
            _, _, last_trail = _word_core(words[b - 1])
            src = " ".join(run) if b - a == 1 else " ".join(words[a:b])[len(first_lead):]
            src = src[: len(src) - len(last_trail)] if last_trail and b - a > 1 else src
            has_op = any(c in _OP_WORDS for c in cores[a:b]) or any(
                re.search(r"[=→±√]|[A-Za-z0-9²³][+\-−/][A-Za-z0-9]", c) for c in cores[a:b])
            latex = to_latex(src) if has_op else ""
            out += words[i:a]
            if latex:
                out.append(first_lead + r"\(" + latex + r"\)" + last_trail)
                found = True
            else:
                out += words[a:b]
            out += words[b:j]
        else:
            out += words[i:j]
        i = j
    return " ".join(out) if found else ""
