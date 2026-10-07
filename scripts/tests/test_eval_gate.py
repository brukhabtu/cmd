"""The gate reads the shape `claude plugin eval --json` writes (plugin-evals reference)."""

from typing import Any

from eval_gate import failures


def result(*cases: dict[str, Any], partial: bool = False) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "partial": partial,
        "partialReason": "cost ceiling" if partial else None,
        "aggregates": {"overallScore": 1.0, "casesPassed": len(cases), "casesTotal": len(cases)},
        "cases": list(cases),
    }


def case(name: str, score: float | None, delta: float | None) -> dict[str, Any]:
    return {"name": name, "aggregates": {"score": score, "delta": delta}}


def test_a_perfect_case_with_a_positive_delta_passes() -> None:
    assert failures(result(case("gpui-hover", 1.0, 0.67))) == []


def test_a_case_below_threshold_fails() -> None:
    assert failures(result(case("gpui-hover", 0.67, 0.5))) == [
        "gpui-hover: score 0.67 is below 1.0"
    ]


def test_a_case_the_skill_does_not_change_fails() -> None:
    assert failures(result(case("a", 1.0, 0.0))) == ["a: delta 0.0 means the skill changed nothing"]
    assert failures(result(case("b", 1.0, -0.3))) == [
        "b: delta -0.3 means the skill changed nothing"
    ]


def test_a_run_without_ablation_fails_and_says_how_to_fix_it() -> None:
    assert failures(result(case("a", 1.0, None))) == [
        "a: no ablation delta; run with --ablation with-without"
    ]


def test_a_partial_run_fails_even_when_every_case_passed() -> None:
    assert failures(result(case("a", 1.0, 0.5), partial=True)) == ["partial run: cost ceiling"]
