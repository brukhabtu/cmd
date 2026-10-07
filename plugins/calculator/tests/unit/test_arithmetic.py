from fractions import Fraction

import pytest
from calculator.arithmetic import evaluate, render


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2+2", Fraction(4)),
        ("2 + 2 * 3", Fraction(8)),
        ("(2 + 2) * 3", Fraction(12)),
        ("10 / 4", Fraction(5, 2)),
        ("0.1 + 0.2", Fraction(3, 10)),
        ("2 ^ 10", Fraction(1024)),
        ("2 ^ 3 ^ 2", Fraction(512)),
        ("-3 * -2", Fraction(6)),
        ("-(2 + 3)", Fraction(-5)),
        ("4 ^ -1", Fraction(1, 4)),
    ],
)
def test_evaluates_arithmetic(text: str, expected: Fraction) -> None:
    assert evaluate(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "hello",
        "2 +",
        "+",
        "(2 + 3",
        "2 + 3)",
        "1 / 0",
        "2 ^ 0.5",
        "2 ^ 5000",
        "0 ^ -1",
        "4",
        "2 x 3",
    ],
)
def test_text_that_is_not_arithmetic_evaluates_to_none(text: str) -> None:
    assert evaluate(text) is None


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (Fraction(4), "4"),
        (Fraction(-12), "-12"),
        (Fraction(5, 2), "2.5"),
        (Fraction(1, 3), "0.3333333333"),
    ],
)
def test_render(value: Fraction, shown: str) -> None:
    assert render(value) == shown
