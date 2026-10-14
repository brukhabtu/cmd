import pytest
from watchdemo.options import DEFAULT_INTERVAL, MIN_INTERVAL, parse_options
from watchdemo.tickets import Ticket, TicketsError, find, narrowed_id, parse_tickets, score

A = Ticket("PROJ-1", "Fix the login page", "Open", "https://example.test/PROJ-1")
B = Ticket("PROJ-2", "Login emails bounce", "In Review")
C = Ticket("OPS-10", "Rotate the keys", "Done")
ALL = (A, B, C)


def test_parse_reads_the_fields_and_the_optional_url() -> None:
    tickets = parse_tickets([
        {"id": "A-1", "title": "One", "status": "Open", "url": "https://x.test/1"},
        {"id": " A-2 ", "title": "Two", "status": "Done"},
    ])
    assert tickets == (
        Ticket("A-1", "One", "Open", "https://x.test/1"),
        Ticket("A-2", "Two", "Done", None),
    )


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"id": "A"}, "expected a list of tickets, found an object"),
        (None, "found null"),
        ([1], "ticket 1: expected an object, found a number"),
        ([{"title": "t", "status": "s"}], "ticket 1: 'id' must be non-empty text"),
        ([{"id": "a", "title": " ", "status": "s"}], "ticket 1: 'title' must be non-empty text"),
        ([{"id": "a", "title": "t", "status": 3}], "'status' must be non-empty text"),
        ([{"id": "a", "title": "t", "status": "s", "url": ""}], "'url' must be non-empty text"),
        ([{"id": "a", "title": "t", "status": "s", "url": 7}], "'url' must be non-empty text"),
        (
            [{"id": "a", "title": "t", "status": "s"}, {"id": "a", "title": "u", "status": "s"}],
            "ticket 2: the id 'a' appears twice",
        ),
    ],
)
def test_parse_names_what_is_wrong(raw: object, message: str) -> None:
    with pytest.raises(TicketsError, match=message):
        parse_tickets(raw)


def test_an_empty_list_is_valid() -> None:
    assert parse_tickets([]) == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("proj-1", 1.0),
        ("proj", 0.9),
        ("-1", 0.8),
        ("fix", 0.7),
        ("login", 0.6),
        ("age", 0.5),
        ("zzz", None),
    ],
)
def test_score_ranks_id_over_title_and_start_over_middle(text: str, expected: float | None) -> None:
    assert score(A, text) == expected


def test_score_ignores_case_and_surrounding_space() -> None:
    assert score(A, "  PROJ-1 ") == pytest.approx(1.0)


def test_blank_text_matches_everything() -> None:
    assert [match.ticket for match in find(ALL, "")] == [C, A, B]


def test_find_ranks_the_id_match_above_a_title_match() -> None:
    # "login": a word in A's title (0.6) and the start of B's title (0.7).
    assert [match.ticket for match in find(ALL, "login")] == [B, A]


def test_find_breaks_ties_by_id() -> None:
    assert [m.ticket.id for m in find((B, A), "proj")] == ["PROJ-1", "PROJ-2"]


def test_find_matches_a_title_substring_case_insensitively() -> None:
    assert [m.ticket.id for m in find(ALL, "KEYS")] == ["OPS-10"]


def test_find_does_not_treat_the_text_as_a_pattern() -> None:
    assert find(ALL, ".*") == ()
    assert find(ALL, "(") == ()


@pytest.mark.parametrize(
    ("text", "word"),
    [("PROJ-1 ", "PROJ-1"), ("PROJ-1  ", "PROJ-1"), (" PROJ-1 ", "PROJ-1"), ("PROJ-1", None)],
)
def test_narrowed_id_is_one_word_and_a_space(text: str, word: str | None) -> None:
    assert narrowed_id(text) == word


def test_an_id_and_a_space_narrows_to_that_ticket_alone() -> None:
    # "PROJ-1" alone would also match PROJ-2's title? It does not; use a prefix to show it.
    assert [m.ticket.id for m in find(ALL, "PROJ-1")] == ["PROJ-1"]
    assert [m.ticket.id for m in find(ALL, "login")] == ["PROJ-2", "PROJ-1"]
    ticket = Ticket("login", "Two", "x")
    assert [m.ticket for m in find((*ALL, ticket), "login ")] == [ticket]
    assert [m.score for m in find((*ALL, ticket), "login ")] == [1.0]


def test_narrowing_ignores_case_and_beats_a_prefix_search() -> None:
    longer = Ticket("PROJ-10", "Another", "Open")
    assert [m.ticket.id for m in find((A, longer), "proj-1 ")] == ["PROJ-1"]
    assert [m.ticket.id for m in find((A, longer), "proj-1")] == ["PROJ-1", "PROJ-10"]


def test_a_word_and_a_space_that_is_no_id_is_searched() -> None:
    assert [m.ticket.id for m in find(ALL, "login ")] == ["PROJ-2", "PROJ-1"]


def test_options_default_when_only_tickets_is_given() -> None:
    settings = parse_options({"tickets": "tickets.json"})
    assert (settings.tickets, settings.interval, settings.notes) == (
        "tickets.json",
        DEFAULT_INTERVAL,
        (),
    )


def test_options_without_tickets_say_what_to_set() -> None:
    settings = parse_options({})
    assert settings.tickets is None
    assert "set `tickets`" in settings.notes[0]


@pytest.mark.parametrize("bad", [3, "", "  ", ["a"]])
def test_options_with_a_bad_tickets_value_have_no_tickets(bad: object) -> None:
    settings = parse_options({"tickets": bad})
    assert settings.tickets is None
    assert settings.notes


def test_interval_is_raised_to_the_minimum_with_a_note() -> None:
    settings = parse_options({"tickets": "t", "interval": 0.1})
    assert settings.interval == MIN_INTERVAL
    assert "at least 0.5" in settings.notes[0]


def test_interval_accepts_an_integer_and_the_minimum() -> None:
    assert parse_options({"tickets": "t", "interval": 2}).interval == pytest.approx(2.0)
    assert parse_options({"tickets": "t", "interval": 0.5}).notes == ()


@pytest.mark.parametrize("bad", ["5", True, float("nan"), float("inf"), None])
def test_interval_that_is_no_number_falls_back_with_a_note(bad: object) -> None:
    settings = parse_options({"tickets": "t", "interval": bad})
    assert settings.interval == DEFAULT_INTERVAL
    assert settings.tickets == "t"
    assert "interval" in settings.notes[0]
