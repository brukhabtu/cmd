import json

from watchdemo.sample import SAMPLE_TICKETS, STATUSES, moved_on, next_status, tickets_text
from watchdemo.tickets import Ticket, parse_tickets


def test_a_status_goes_round_the_list_and_an_unknown_one_starts_it() -> None:
    assert [next_status(s) for s in STATUSES] == ["In Review", "Done", "Open"]
    assert next_status("Blocked") == STATUSES[0]


def test_the_sample_text_reads_back_as_the_same_tickets() -> None:
    assert parse_tickets(json.loads(tickets_text(SAMPLE_TICKETS))) == SAMPLE_TICKETS


def test_the_text_keeps_a_url_only_when_there_is_one() -> None:
    both = (Ticket("A-1", "One", "Open", "https://example.test/A-1"), Ticket("A-2", "Two", "Open"))
    entries = json.loads(tickets_text(both))
    assert entries[0]["url"] == "https://example.test/A-1"
    assert "url" not in entries[1]


def test_moving_on_changes_only_the_named_ticket() -> None:
    moved = moved_on(SAMPLE_TICKETS, "DEMO-1")
    assert moved is not None
    assert [t.status for t in moved] == ["In Review", "In Review", "Done"]
    assert [t.id for t in moved] == [t.id for t in SAMPLE_TICKETS]


def test_moving_on_a_ticket_that_is_not_there_is_none() -> None:
    assert moved_on(SAMPLE_TICKETS, "NOPE-1") is None
