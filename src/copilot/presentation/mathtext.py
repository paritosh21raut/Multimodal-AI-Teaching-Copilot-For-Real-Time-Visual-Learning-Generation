"""Plain-text formula → LaTeX for KaTeX (F-007a). Pure and deterministic; no LLM.

The model writes formulas as plain text ("6CO2 + 6H2O → C6H12O6 + 6O2", "Cardiac Output = Heart Rate × Stroke
Volume", "carbon dioxide plus water, in the presence of sunlight, gives glucose plus oxygen"). Words and chemical
formulas become ``\\text{}`` (the display styles it with the slide font), single-letter variables stay math italics.
``to_latex`` returns "" when it cannot build a safe expression; the display then shows the spoken form.
"""
from __future__ import annotations

import re

ELEMENTS = frozenset("""H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se
Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W
Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr""".split())
# single-element molecules written with a count (O2, O3, S8, P4); anything else alone (B12, N95, U2) is not chemistry
_ELEMENTAL = frozenset("H N O F Cl Br I S P".split())

_CHEM = re.compile(r"^(?P<coef>\d*)(?P<body>(?:[A-Z][a-z]?\d*)+)$")
_PART = re.compile(r"([A-Z][a-z]?)(\d*)")

GREEK = {name: "\\" + name for name in (
    "alpha beta gamma delta epsilon theta lambda mu pi rho sigma tau phi omega "
    "Gamma Delta Theta Lambda Pi Sigma Phi Omega").split()}
GREEK.update({"α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\epsilon", "θ": r"\theta",
              "λ": r"\lambda", "μ": r"\mu", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "φ": r"\phi",
              "ω": r"\omega", "Δ": r"\Delta", "Σ": r"\Sigma", "Ω": r"\Omega"})

_SUPERSCRIPTS = {"²": "^2", "³": "^3", "⁴": "^4", "¹": "^1", "⁰": "^0"}

# spoken operators → symbols (order matters: longer phrases first)
_PHRASES = [
    (r"\bis equal to\b", "="), (r"\bequals\b", "="), (r"\bgives us\b", "→"), (r"\bgives\b", "→"),
    (r"\bproduces\b", "→"), (r"\byields\b", "→"), (r"\bforms\b", "→"), (r"\bplus\b", "+"), (r"\bminus\b", "−"),
    (r"(?<=\b[A-Za-z0-9]) into (?=[A-Za-z0-9]\b)", "×"),  # Indian English "m into a" = m × a (symbols only)
    (r"\bhalf\b(?= ?[A-Za-z])", "1/2 "), (r"\bmultiplied by\b", "×"), (r"\btimes\b", "×"), (r"\bdivided by\b", "/"), (r"\bsquared\b", "^2"),
    (r"\bcubed\b", "^3"),
]
_ARROWS = re.compile(r"\s*(?:-+>|=+>|⟶|⇒|→)\s*")
_CONDITION = re.compile(r",?\s*\bin the presence of\b\s+(?P<c>[^,→=]+?)\s*,?\s*(?=→)", re.IGNORECASE)

_OPS = {"+": "+", "−": "-", "-": "-", "×": r"\times", "*": r"\times", "·": r"\cdot", "÷": r"\div", "=": "=",
        "≈": r"\approx", "≠": r"\neq", "≤": r"\leq", "≥": r"\geq", "<": "<", ">": ">", "∝": r"\propto",
        "→": r"\rightarrow", ",": ",\\;", "(": "(", ")": ")"}
_TOKEN = re.compile(r"\s*(→|≈|≠|≤|≥|∝|[+\-−×*·÷=<>/^(),]|[^+\-−×*·÷=<>/^(),→≈≠≤≥∝]+)")
_WORD_HYPHEN = re.compile(r"(?<=[A-Za-z])-(?=[a-z]{2})")
_LATEX_LIKE = re.compile(r"\\[A-Za-z]+|[_^]\{")
_TEXT_ESCAPE = str.maketrans({"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
                              "#": r"\#", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"})
_UNSAFE = re.compile(r"\\(?:href|url|html\w*|includegraphics|def|gdef|newcommand|renewcommand|let)\b")
_MAX_LEN = 300


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


def _chem_latex(token: str) -> str | None:
    """'6CO2' → 6 CO₂ with every part (digits too) as text, so the whole formula is in the slide font."""
    parts = chem_parts(token)
    if parts is None:
        return None
    coef = _CHEM.match(token).group("coef")  # type: ignore[union-attr]
    body, run = "", ""
    for sym, n in parts:  # one text run until a count
        run += sym
        if n:
            body += _text(run) + "_{" + _text(n) + "}"
            run = ""
    body += _text(run) if run else ""
    return (_text(coef) + r"\," if coef else "") + body


def _operand(chunk: str, symbolic: bool) -> str:
    """One operand between operators: a number, chemical formula, variable(s), Greek letter or words."""
    s = chunk.strip()
    if not s:
        return ""
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return s.replace(",", "{,}")
    if s in GREEK:
        return GREEK[s]
    chem = _chem_latex(s) if " " not in s else None
    if chem:
        return chem
    if symbolic and " " in s:  # "2 m v" in a symbolic formula: a product of terms
        return " ".join(_operand(p, True) for p in s.split())
    m = re.fullmatch(r"(\d*)\s*([A-Za-z]{1,3})", s)
    if m and (len(m.group(2)) == 1 or (symbolic and m.group(2).islower())):
        # "v", "2a", and in a symbolic formula "mc" or "at" (products of variables)
        return m.group(1) + (r"\," if m.group(1) else "") + " ".join(m.group(2))
    m = re.fullmatch(r"([A-Za-z])_?(\d+|[a-z])", s)  # v0, x2, v_f → subscripted variable
    if m and symbolic:
        return f"{m.group(1)}_{{{m.group(2)}}}"
    m = re.fullmatch(r"(Δ|Delta|delta)\s*([A-Za-z])", s)
    if m:
        return r"\Delta " + m.group(2)
    m = re.fullmatch(r"√\s*(.+)", s)
    if m:
        return r"\sqrt{" + _operand(m.group(1), symbolic) + "}"
    return _text(" ".join(s.split()))


def _is_symbolic(chunks: list[str]) -> bool:
    """A formula written in symbols (F = ma), not in words (speed = distance / time)."""
    words = [w for c in chunks for w in c.split()]
    singles = [w for w in words if re.fullmatch(r"\d*\s*[A-Za-z]", w) or w in GREEK]
    return bool(singles) and all(len(w) <= 3 or w in GREEK or chem_parts(w.replace(" ", "")) for w in words)


def _normalise(expr: str) -> tuple[str, str]:
    s = " ".join(expr.replace("−", "−").split()).rstrip(". ")
    label, colon, rest = s.partition(":")
    if colon and "=" in rest and "=" not in label and len(label.split()) <= 4:
        s = rest.strip()  # "Ohm's law: V = IR" → the formula; the slide title names it
    for k, v in _SUPERSCRIPTS.items():
        s = s.replace(k, v)
    s = _WORD_HYPHEN.sub("‐", s)  # "x-ray", "carbon-dioxide": a hyphen inside a word is not a minus
    for pat, rep in _PHRASES:
        s = re.sub(pat, f" {rep} ", s, flags=re.IGNORECASE)
    s = _ARROWS.sub(" → ", s)
    s = " ".join(s.split())
    condition = ""
    m = _CONDITION.search(s)
    if m:
        condition = m.group("c").strip()
        s = (s[: m.start()] + " " + s[m.end():]).strip()
    return s, condition


def to_latex(expr: str) -> str:
    """Plain formula text → KaTeX LaTeX, or "" when no safe expression can be built."""
    expr = (expr or "").strip()
    if not expr or len(expr) > _MAX_LEN:
        return ""
    if _LATEX_LIKE.search(expr):
        return expr if _balanced(expr) and not _UNSAFE.search(expr) else ""
    s, condition = _normalise(expr)
    tokens = _TOKEN.findall(s)
    if re.sub(r"\s", "", "".join(tokens)) != re.sub(r"\s", "", s):
        return ""
    # symbols or words, decided per side of = / → ("Kinetic energy = 1/2 m v^2": words, then symbols)
    sides: list[list[str]] = [[]]
    for t in tokens:
        if t.strip() in ("=", "→"):
            sides.append([])
        elif t.strip() not in _OPS and t.strip() not in "/^":
            sides[-1].append(t)
    side_symbolic = [_is_symbolic(chunks) for chunks in sides]
    if any(side_symbolic):  # "F = ma": a side of short letter groups next to a symbolic side is symbolic too
        side_symbolic = [sym or all(len(w) <= 3 for c in chunks for w in c.split()) for sym, chunks in
                         zip(side_symbolic, sides)]
    side = 0
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i].strip()
        symbolic = side_symbolic[side]
        if t in ("=", "→"):
            side += 1
        if t == "^" and i + 1 < len(tokens):
            out.append("^{" + _operand(tokens[i + 1], True) + "}")
            i += 2
            continue
        if t == "/":
            # a simple a / b becomes a fraction; anything else keeps the slash
            if out and i + 1 < len(tokens) and tokens[i + 1].strip() not in _OPS:
                num = out.pop()
                den, _, rest = tokens[i + 1].strip().partition(" ") if symbolic else (tokens[i + 1], "", "")
                out.append(r"\dfrac{" + num + "}{" + _operand(den, symbolic) + "}")  # "1/2 m v^2": only "2"
                if rest:
                    out.append(_operand(rest, symbolic))
                i += 2
                continue
            out.append("/")
        elif t == "→":
            out.append(r"\xrightarrow{" + _text(condition) + "}" if condition else r"\rightarrow")
            condition = ""
        elif t in _OPS:
            out.append(_OPS[t])
        else:
            out.append(_operand(t, symbolic))
        i += 1
    latex = " ".join(x for x in out if x)
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
