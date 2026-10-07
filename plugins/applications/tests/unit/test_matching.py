import pytest
from applications.matching import INEXACT_CEILING, score

NAMES = ("Safari", "Visual Studio Code", "Terminal", "Activity Monitor", "1+1", "iTerm")


def must(query: str, name: str) -> float:
    found = score(query, name)
    assert found is not None, f"{query!r} should match {name!r}"
    return found


@pytest.mark.parametrize("query", ["Safari", "safari", "SAFARI", "  safari "])
def test_the_whole_name_is_the_best_score_whatever_the_case(query: str) -> None:
    assert score(query, "Safari") == pytest.approx(1.0)


def test_an_exact_name_beats_a_prefix_beats_initials_beats_a_scattered_subsequence() -> None:
    exact = must("visual studio code", "Visual Studio Code")
    prefix = must("visual", "Visual Studio Code")
    initials = must("vsc", "Visual Studio Code")
    scattered = must("iuo", "Visual Studio Code")
    assert exact > prefix > initials > scattered


def test_a_longer_prefix_scores_higher_than_a_shorter_one() -> None:
    assert must("safar", "Safari") > must("saf", "Safari") > must("sa", "Safari")


def test_initials_land_on_word_starts_rather_than_inner_letters() -> None:
    # The s in Visual would give a tighter but less anchored match than the S of Studio.
    assert must("vsc", "Visual Studio Code") > must("vsu", "Visual Studio Code")


def test_case_never_matters() -> None:
    assert must("SAF", "safari") == must("saf", "SAFARI") == must("Saf", "Safari")


@pytest.mark.parametrize(
    ("query", "name"),
    [("x", "Safari"), ("fas", "Safari"), ("safarii", "Safari"), ("term", "1+1")],
)
def test_text_that_is_not_a_subsequence_does_not_match(query: str, name: str) -> None:
    assert score(query, name) is None


@pytest.mark.parametrize("query", ["", "   "])
def test_a_blank_query_matches_nothing(query: str) -> None:
    assert all(score(query, name) is None for name in NAMES)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("query", ["s", "sa", "saf", "vsc", "te", "am", "1", "term", "it"])
def test_every_score_lies_in_the_unit_interval_and_inexact_ones_below_the_ceiling(
    query: str, name: str
) -> None:
    found = score(query, name)
    if found is None:
        return
    assert 0.0 < found <= 1.0
    if query.casefold() != name.casefold():
        assert found <= INEXACT_CEILING < 1.0
