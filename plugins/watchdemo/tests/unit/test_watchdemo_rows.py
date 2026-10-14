import pytest
from cmd_sdk import Action
from watchdemo.rows import (
    HOME_CHANGES,
    actions_for,
    complete_text,
    home_rows,
    query_rows,
    ticket_item,
)
from watchdemo.state import Change, State
from watchdemo.tickets import Ticket

A = Ticket("PROJ-1", "Fix the login page", "Open", "https://example.test/PROJ-1")
B = Ticket("PROJ-2", "Login emails bounce", "In Review")
TICKETS = (A, B)
WATCHING_A = State(frozenset({"PROJ-1"}), {"PROJ-1": "Open"})


def ids(items: tuple) -> list[str]:  # type: ignore[type-arg]
    return [item.id for item in items]


def test_a_ticket_row_completes_to_its_id_and_has_the_actions() -> None:
    item = ticket_item(A, watched=False, score=0.9)
    assert item.id == "PROJ-1"
    assert item.title == "PROJ-1  Fix the login page"
    assert item.subtitle == "Open"
    assert item.score == pytest.approx(0.9)
    assert item.complete == "watch PROJ-1 "
    assert item.actions == (
        Action("open", "Open"),
        Action("watch", "Watch"),
        Action("copy", "Copy id"),
    )


def test_a_watched_ticket_offers_unwatch_and_says_so() -> None:
    item = ticket_item(A, watched=True)
    assert item.subtitle == "Open · watching"
    assert [a.id for a in item.actions] == ["open", "unwatch", "copy"]


def test_a_ticket_with_no_url_copies_its_id_instead_of_opening() -> None:
    assert actions_for(url=None, watched=False) == (
        Action("copy", "Copy id"),
        Action("watch", "Watch"),
    )


def test_complete_text_is_the_keyword_the_id_and_a_space() -> None:
    assert complete_text("PROJ-1") == "watch PROJ-1 "


def test_a_search_returns_the_matches_and_the_watching_suggestion_after_them() -> None:
    items = query_rows("login", TICKETS, WATCHING_A)
    assert ids(items) == ["PROJ-2", "PROJ-1"]  # "login" is not a prefix of "watching"


def test_blank_text_lists_every_ticket_and_the_suggestion() -> None:
    items = query_rows("", TICKETS, WATCHING_A)
    assert ids(items) == ["PROJ-1", "PROJ-2", ""]
    suggestion = items[-1]
    assert suggestion.title == "Watching (1)"
    assert suggestion.complete == "watch watching"
    assert suggestion.actions == ()
    assert suggestion.score is None


def test_a_prefix_of_watching_offers_the_suggestion() -> None:
    items = query_rows("wat", TICKETS, State())
    assert [item.title for item in items] == ["Watching (0)"]
    assert items[0].complete == "watch watching"


def test_watching_lists_the_watched_tickets_with_their_status() -> None:
    items = query_rows("watching", TICKETS, WATCHING_A)
    assert [(item.id, item.subtitle) for item in items] == [("PROJ-1", "Open · watching")]


def test_watching_lists_a_watched_ticket_the_file_no_longer_holds() -> None:
    state = State(frozenset({"GONE-1", "PROJ-2"}), {})
    items = query_rows("watching", TICKETS, state)
    assert ids(items) == ["PROJ-2", "GONE-1"]
    assert [a.id for a in items[1].actions] == ["unwatch"]
    assert items[1].complete is None


def test_watching_with_nothing_watched_says_so() -> None:
    (item,) = query_rows("watching", TICKETS, State())
    assert item.title == "Nothing is watched yet"
    assert item.actions == ()


def test_an_id_and_a_space_narrows_to_that_ticket() -> None:
    items = query_rows("PROJ-2 ", TICKETS, State())
    assert ids(items) == ["PROJ-2"]
    assert [a.id for a in items[0].actions] == ["watch", "copy"]


def test_a_search_that_finds_one_ticket_is_not_narrowing() -> None:
    (item,) = query_rows("bounce", TICKETS, State())
    assert [a.id for a in item.actions] == ["copy", "watch"]


def test_toggle_first_puts_the_toggle_ahead_of_open_and_copy() -> None:
    assert [a.id for a in actions_for(url="u", watched=True, toggle_first=True)] == [
        "unwatch",
        "open",
        "copy",
    ]


def test_no_match_is_a_row_that_says_so() -> None:
    (item,) = query_rows("zzz", TICKETS, State())
    assert item.title == "No ticket matches 'zzz'"
    assert item.complete is None
    assert item.actions == ()


def test_an_unusable_file_is_its_problems_and_nothing_else() -> None:
    items = query_rows("login", None, State(), problems=["/x.json does not exist"])
    assert [item.title for item in items] == ["/x.json does not exist"]
    assert all(not item.actions and item.complete is None for item in items)


def test_notes_follow_a_blank_query_only() -> None:
    assert query_rows("", TICKETS, State(), notes=["a note"])[-1].title == "a note"
    assert "a note" not in [
        item.title for item in query_rows("login", TICKETS, State(), notes=["a note"])
    ]


def change(id_: str, number: int) -> Change:
    return Change(id_, f"Title of {id_}", "Open", "Done", f"2026-10-14T19:00:{number:02d}")


def test_home_shows_what_moved_newest_first_then_what_is_watched() -> None:
    state = State(
        frozenset({"PROJ-1"}),
        {"PROJ-1": "Done"},
        (change("PROJ-2", 9), change("PROJ-1", 3)),
    )
    items = home_rows(TICKETS, state)
    assert [item.title for item in items] == [
        "PROJ-2: Open -> Done",
        "PROJ-1: Open -> Done",
        "PROJ-1  Fix the login page",
    ]
    assert items[0].subtitle == "Title of PROJ-2 · 2026-10-14 19:00:09"
    assert [a.id for a in items[0].actions] == ["copy", "watch"]  # PROJ-2: no url, not watched
    assert [a.id for a in items[1].actions] == ["open", "unwatch", "copy"]


def test_home_limits_the_changes_shown() -> None:
    state = State(recent=tuple(change(f"T{n}", n) for n in range(HOME_CHANGES + 4)))
    assert len(home_rows(TICKETS, state)) == HOME_CHANGES


def test_home_with_nothing_to_show_explains_and_completes() -> None:
    (item,) = home_rows(TICKETS, State())
    assert item.title == "Nothing watched yet"
    assert item.complete == "watch "


def test_home_with_an_unusable_file_leads_with_the_problem_and_keeps_the_changes() -> None:
    state = State(recent=(change("PROJ-1", 1),))
    items = home_rows(None, state, problems=["no file"])
    assert [item.title for item in items] == ["no file", "PROJ-1: Open -> Done"]
