import pytest
from watchdemo.diff import Notice, diff, long_gap, plan_notices
from watchdemo.state import (
    RECENT_LIMIT,
    Change,
    State,
    StateError,
    state_from_json,
    state_to_json,
    unwatch,
    watch,
)
from watchdemo.tickets import Ticket

AT = "2026-10-14T19:00:00"


def ticket(id_: str, status: str, url: str | None = None) -> Ticket:
    return Ticket(id_, f"Title of {id_}", status, url)


def test_the_first_sight_of_a_watched_ticket_records_and_does_not_change() -> None:
    result = diff(State(watched=frozenset({"A"})), [ticket("A", "Open")], AT)
    assert result.changes == ()
    assert result.state.seen == {"A": "Open"}
    assert result.state.recent == ()


def test_a_different_status_is_a_change_and_is_recorded_newest_first() -> None:
    state = State(watched=frozenset({"A"}), seen={"A": "Open"})
    result = diff(state, [ticket("A", "Done")], AT)
    assert result.changes == (Change("A", "Title of A", "Open", "Done", AT),)
    assert result.state.seen == {"A": "Done"}
    again = diff(result.state, [ticket("A", "Reopened")], "later")
    assert [c.new for c in again.state.recent] == ["Reopened", "Done"]


def test_the_same_status_changes_nothing_and_returns_the_same_state() -> None:
    state = State(watched=frozenset({"A"}), seen={"A": "Open"})
    result = diff(state, [ticket("A", "Open")], AT)
    assert result.changes == ()
    assert result.state is state


def test_an_unwatched_ticket_that_moved_is_ignored() -> None:
    state = State(watched=frozenset({"A"}), seen={"A": "Open"})
    result = diff(state, [ticket("A", "Open"), ticket("B", "Done")], AT)
    assert result.changes == ()
    assert "B" not in result.state.seen


def test_a_watched_ticket_missing_from_the_file_keeps_its_status() -> None:
    state = State(watched=frozenset({"A"}), seen={"A": "Open"})
    gone = diff(state, [ticket("Z", "Open")], AT)
    assert gone.changes == ()
    assert gone.state is state
    back = diff(gone.state, [ticket("A", "Open")], AT)
    assert back.changes == ()


def test_several_tickets_moving_in_one_poll_are_all_changes_in_file_order() -> None:
    state = State(watched=frozenset({"A", "B", "C"}), seen={"A": "1", "B": "1", "C": "1"})
    result = diff(state, [ticket("B", "2"), ticket("A", "2"), ticket("C", "1")], AT)
    assert [c.id for c in result.changes] == ["B", "A"]
    assert [c.id for c in result.state.recent] == ["B", "A"]


def test_the_recent_list_is_bounded() -> None:
    state = State(watched=frozenset({"A"}), seen={"A": "0"})
    for number in range(1, RECENT_LIMIT + 11):
        state = diff(state, [ticket("A", str(number))], AT).state
    assert len(state.recent) == RECENT_LIMIT
    assert state.recent[0].new == str(RECENT_LIMIT + 10)
    assert state.recent[-1].new == "11"


def test_watch_records_the_status_when_known_and_is_idempotent() -> None:
    state = watch(State(), "A", "Open")
    assert state.watched == {"A"}
    assert state.seen == {"A": "Open"}
    assert watch(state, "A", "Done") is state


def test_watch_without_a_known_status_leaves_it_to_the_first_poll() -> None:
    assert watch(State(), "A", None).seen == {}


def test_unwatch_forgets_the_status_and_keeps_the_history() -> None:
    change = Change("A", "t", "x", "y", AT)
    state = State(frozenset({"A", "B"}), {"A": "y", "B": "z"}, (change,))
    after = unwatch(state, "A")
    assert after.watched == {"B"}
    assert after.seen == {"B": "z"}
    assert after.recent == (change,)
    assert unwatch(after, "A") is after


def test_a_ticket_moving_between_watch_and_the_first_poll_is_noticed() -> None:
    state = watch(State(), "A", "Open")
    assert diff(state, [ticket("A", "Done")], AT).changes


def test_state_round_trips_through_json() -> None:
    state = State(frozenset({"A", "B"}), {"A": "Open"}, (Change("A", "t", "x", "Open", AT),))
    assert state_from_json(state_to_json(state)) == state


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {"version": 2, "watched": [], "seen": {}, "recent": []},
        {"version": 1, "seen": {}, "recent": []},
        {"version": 1, "watched": "A", "seen": {}, "recent": []},
        {"version": 1, "watched": [1], "seen": {}, "recent": []},
        {"version": 1, "watched": ["A"], "seen": {"A": 1}, "recent": []},
        {"version": 1, "watched": [], "seen": {"A": "x"}, "recent": []},
        {"version": 1, "watched": [], "seen": {}, "recent": {}},
        {"version": 1, "watched": [], "seen": {}, "recent": [{"id": "A"}]},
    ],
)
def test_state_from_json_refuses_what_it_did_not_write(raw: object) -> None:
    with pytest.raises(StateError):
        state_from_json(raw)


def test_state_from_json_keeps_at_most_the_limit() -> None:
    entry = {"id": "A", "title": "t", "old": "x", "new": "y", "at": AT}
    raw = {"version": 1, "watched": [], "seen": {}, "recent": [entry] * (RECENT_LIMIT + 5)}
    assert len(state_from_json(raw).recent) == RECENT_LIMIT


def change(id_: str) -> Change:
    return Change(id_, f"Title of {id_}", "Open", "Done", AT)


def test_each_change_is_a_notice_with_the_url_of_its_ticket() -> None:
    tickets = [ticket("A", "Done", "https://x.test/A"), ticket("B", "Done")]
    assert plan_notices([change("A"), change("B")], tickets, slept=5, interval=5) == (
        Notice("A", "A moved", "Open -> Done", "https://x.test/A"),
        Notice("B", "B moved", "Open -> Done", None),
    )


def test_no_changes_no_notices() -> None:
    assert plan_notices([], [], slept=1000, interval=5) == ()


def test_many_changes_after_a_long_gap_are_one_summary() -> None:
    changes = [change(name) for name in "ABCD"]
    notices = plan_notices(changes, [], slept=16, interval=5)
    assert notices == (Notice("summary", "4 tickets moved", "A, B, C, D"),)


def test_the_summary_names_a_few_and_counts_the_rest() -> None:
    changes = [change(f"T{number}") for number in range(8)]
    (notice,) = plan_notices(changes, [], slept=999, interval=5)
    assert notice.title == "8 tickets moved"
    assert notice.body == "T0, T1, T2, T3, T4 and 3 more"


def test_three_changes_after_a_long_gap_are_still_one_each() -> None:
    changes = [change(name) for name in "ABC"]
    assert len(plan_notices(changes, [], slept=999, interval=5)) == 3


def test_many_changes_in_an_ordinary_poll_are_one_each() -> None:
    changes = [change(name) for name in "ABCDE"]
    assert len(plan_notices(changes, [], slept=5.2, interval=5)) == 5


def test_a_gap_is_long_only_above_three_intervals() -> None:
    assert not long_gap(15, 5)
    assert long_gap(15.01, 5)
