"""Exact arithmetic on text: ``+ - * / ^``, parentheses, and unary minus.

A recursive-descent parser over ``Fraction``, so ``0.1 + 0.2`` is ``0.3``. Text that is
not an expression evaluates to ``None``; that is the ordinary case in a launcher, not an
error.
"""

import re
from fractions import Fraction

_LEXEME = re.compile(r"\s*(\d+(?:\.\d+)?|\.\d+|[-+*/^()])")
_MAX_EXPONENT = 1000


def evaluate(text: str) -> Fraction | None:
    """Evaluate ``text``, or return ``None`` when it is not arithmetic."""
    tokens = _tokenize(text)
    if not tokens or not any(lexeme in "+-*/^" for lexeme in tokens):
        return None
    parsed = _sum(tokens, 0)
    if parsed is None:
        return None
    value, position = parsed
    return value if position == len(tokens) else None


def render(value: Fraction) -> str:
    """Show a value the way a person expects: integers plain, otherwise a short decimal."""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):.10g}"


type _Parsed = tuple[Fraction, int] | None


def _tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    position = 0
    while position < len(text):
        match = _LEXEME.match(text, position)
        if match is None:
            return () if text[position:].strip() else tuple(tokens)
        tokens.append(match.group(1))
        position = match.end()
    return tuple(tokens)


def _sum(tokens: tuple[str, ...], position: int) -> _Parsed:
    parsed = _product(tokens, position)
    while parsed is not None and position_has(tokens, parsed[1], "+-"):
        value, position = parsed
        operator = tokens[position]
        right = _product(tokens, position + 1)
        if right is None:
            return None
        parsed = (value + right[0] if operator == "+" else value - right[0], right[1])
    return parsed


def _product(tokens: tuple[str, ...], position: int) -> _Parsed:
    parsed = _power(tokens, position)
    while parsed is not None and position_has(tokens, parsed[1], "*/"):
        value, position = parsed
        operator = tokens[position]
        right = _power(tokens, position + 1)
        if right is None or (operator == "/" and right[0] == 0):
            return None
        parsed = (value * right[0] if operator == "*" else value / right[0], right[1])
    return parsed


def _power(tokens: tuple[str, ...], position: int) -> _Parsed:
    base = _unary(tokens, position)
    if base is None or not position_has(tokens, base[1], "^"):
        return base
    exponent = _power(tokens, base[1] + 1)
    if exponent is None or exponent[0].denominator != 1 or abs(exponent[0]) > _MAX_EXPONENT:
        return None
    if base[0] == 0 and exponent[0] < 0:
        return None
    return (base[0] ** exponent[0].numerator, exponent[1])


def _unary(tokens: tuple[str, ...], position: int) -> _Parsed:
    if position_has(tokens, position, "-"):
        operand = _unary(tokens, position + 1)
        return None if operand is None else (-operand[0], operand[1])
    if position_has(tokens, position, "+"):
        return _unary(tokens, position + 1)
    return _atom(tokens, position)


def _atom(tokens: tuple[str, ...], position: int) -> _Parsed:
    if position_has(tokens, position, "("):
        inner = _sum(tokens, position + 1)
        if inner is None or not position_has(tokens, inner[1], ")"):
            return None
        return (inner[0], inner[1] + 1)
    if position < len(tokens) and tokens[position][0] in "0123456789.":
        return (Fraction(tokens[position]), position + 1)
    return None


def position_has(tokens: tuple[str, ...], position: int, operators: str) -> bool:
    """Say whether the token at ``position`` is one of ``operators``."""
    return position < len(tokens) and tokens[position] in operators
