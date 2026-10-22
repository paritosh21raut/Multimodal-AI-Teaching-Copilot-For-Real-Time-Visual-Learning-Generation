"""The plot world (F-015 L1): y = f(x) curves from a safe expression parser, sampled by Python, with axes and marked
points. The expression is parsed with `ast` against a whitelist and evaluated by a small tree walker: never eval,
no attribute access, no names but x, pi and e, no calls but a few math functions."""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Callable, Optional

MAX_LEN = 80
_FUNCS: dict[str, Callable[[float], float]] = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp, "log": math.log, "ln": math.log,
    "sqrt": math.sqrt, "abs": abs,
}
_CONSTS = {"pi": math.pi, "e": math.e}
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b}
_UN = {ast.USub: lambda a: -a, ast.UAdd: lambda a: a}


def _normalise(expr: str) -> str:
    s = expr.strip().lower().replace("^", "**").replace("π", "pi").replace("×", "*").replace("−", "-")
    s = re.sub(r"^\s*(?:y|f\s*\(\s*x\s*\))\s*=\s*", "", s)  # "y = x^2" -> "x**2"
    s = re.sub(r"(\d)\s*(x|pi|\(|[a-z]{2,4}\()", r"\1*\2", s)   # 2x, 3(x+1), 2sin(x) -> 2*x ...
    s = re.sub(r"\)\s*(\(|x\b)", r")*\1", s)                    # (x+1)(x-1), (x)x
    return s


def _check(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _check(node.body)
    elif isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        _check(node.left)
        _check(node.right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        _check(node.operand)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        pass
    elif isinstance(node, ast.Name) and (node.id == "x" or node.id in _CONSTS):
        pass
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS \
            and len(node.args) == 1 and not node.keywords:
        _check(node.args[0])
    else:
        raise ValueError(f"not allowed: {type(node).__name__}")


def parse(expr: str) -> ast.Expression:
    """The expression's tree, or ValueError (too long, a syntax error, anything outside the whitelist)."""
    if not expr or len(expr) > MAX_LEN:
        raise ValueError("empty or too long")
    s = _normalise(expr)
    if "__" in s or "lambda" in s:
        raise ValueError("not allowed")
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as err:
        raise ValueError(f"syntax: {err.msg}") from None
    _check(tree)
    return tree


def _eval(node: ast.AST, x: float) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, x)
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left, x), _eval(node.right, x)
        if isinstance(node.op, ast.Pow) and (abs(b) > 64 or abs(a) > 1e6):
            raise OverflowError
        return float(_BIN[type(node.op)](a, b))
    if isinstance(node, ast.UnaryOp):
        return float(_UN[type(node.op)](_eval(node.operand, x)))
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return x if node.id == "x" else _CONSTS[node.id]
    assert isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    return float(_FUNCS[node.func.id](_eval(node.args[0], x)))


def evaluator(expr: str) -> Callable[[float], Optional[float]]:
    """f(x) -> y, None where it is undefined (log of a negative, a division by zero, a complex power)."""
    tree = parse(expr)

    def f(x: float) -> Optional[float]:
        try:
            y = _eval(tree, x)
        except (ArithmeticError, ValueError, TypeError):
            return None
        return y if isinstance(y, float) and math.isfinite(y) else None
    return f


_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def pretty(expr: str) -> str:
    """As printed: "x**2 - 3*x" -> "y = x² − 3x"."""
    s = _normalise(expr).replace(" ", "")
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_SUP), s)
    s = re.sub(r"(\d)\*(?=[a-z(])", r"\1", s).replace("**", "^").replace("*", "·").replace("pi", "π")
    s = re.sub(r"(?<=[^\s(])([+\-])", r" \1 ", s).replace("-", "−")
    return "y = " + s


def nice_step(span: float, n: int = 8) -> float:
    raw = max(span, 1e-9) / n
    p = 10 ** math.floor(math.log10(raw))
    return next(k * p for k in (1, 2, 2.5, 5, 10) if k * p >= raw)


@dataclass
class Sampled:
    xs: list[float]
    ys: list[Optional[float]]


def sample(expr: str, x0: float, x1: float, n: int = 240) -> Sampled:
    f = evaluator(expr)
    xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
    return Sampled(xs, [f(x) for x in xs])


def y_range(curves: list[Sampled]) -> tuple[float, float]:
    """The y window: all finite samples, a steep tail (tan, 1/x) clipped to its 5–95 % band, 0 kept in view."""
    ys = sorted(y for c in curves for y in c.ys if y is not None)
    if not ys:
        return -1.0, 1.0
    lo, hi = ys[0], ys[-1]
    k = len(ys)
    p5, p95 = ys[int(0.05 * (k - 1))], ys[int(0.95 * (k - 1))]
    if hi - lo > 8 * max(p95 - p5, 1e-9):
        lo, hi = p5, p95
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    pad = 0.08 * (hi - lo)
    return lo - pad, hi + pad
