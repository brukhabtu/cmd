from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from vault.outbox import (
    Answered,
    Call,
    Entry,
    EntryError,
    Missed,
    Refused,
    State,
    Step,
    TimedOut,
    Written,
    advance,
    capture_time,
    copied,
    due,
    first_step,
    from_json,
    holds_line,
    missed,
    new_entry,
    on_start,
    render,
    retried,
    soonest,
    to_json,
    writing,
)
from vault.schema import Capture, CaptureKind

NOW = datetime(2026, 10, 8, 14, 30, 5, tzinfo=UTC)
TODO = Capture("todo", CaptureKind.APPEND, "@daily", None, "Tasks", "- [ ] {text}")
NOTE = Capture(
    "note", CaptureKind.APPEND, "Notes/{date} {text}.md", None, None, "- {time} {text} {date}"
)
FORMATS = ("%Y-%m-%d", "%H:%M")


def _entry(**changes: object) -> Entry:
    return replace(new_entry(TODO, "call Sam", NOW, "3f9a1c", FORMATS), **changes)  # type: ignore[arg-type]


def test_a_capture_is_rendered_once_with_its_date_and_time() -> None:
    assert render(NOTE, "  Priya: plan?\nby Friday ", NOW, *FORMATS) == (
        "- 14:30 Priya: plan? by Friday 2026-10-08",
        "Notes/2026-10-08 Priya plan by Friday.md",
    )
    assert render(TODO, "x", NOW, *FORMATS) == ("- [ ] x", "@daily")


def test_a_new_entry_is_pending_due_now_and_named_by_its_time() -> None:
    entry = new_entry(TODO, "call Sam", NOW, "3f9a1c", FORMATS)
    assert entry.id == "20261008T143005-3f9a1c"
    assert entry.state is State.PENDING
    assert entry.next_try == NOW
    assert entry.line == "- [ ] call Sam"
    assert entry.heading == "Tasks"


def test_an_entry_survives_its_file() -> None:
    entry = _entry(
        state=State.UNKNOWN, attempts=2, last_error="x", next_try=NOW + timedelta(seconds=5)
    )
    assert from_json(to_json(entry)) == entry
    assert to_json(_entry())["created"] == "2026-10-08T14:30:05+00:00"


@pytest.mark.parametrize(
    "broken",
    [
        [],
        {**to_json(_entry()), "attempts": -1},
        {**to_json(_entry()), "attempts": True},
        {**to_json(_entry()), "state": "lost"},
        {**to_json(_entry()), "line": None},
        {**to_json(_entry()), "template": 3},
        {**to_json(_entry()), "created": "yesterday"},
    ],
)
def test_a_file_that_is_not_an_entry_says_so(broken: object) -> None:
    with pytest.raises(EntryError):
        from_json(broken)


def test_a_capture_in_the_same_instant_as_the_newest_is_recorded_just_after_it() -> None:
    newest = _entry(created=NOW)
    assert capture_time(NOW, [newest]) == NOW + timedelta(microseconds=1)
    assert capture_time(NOW - timedelta(seconds=1), [newest]) == NOW + timedelta(microseconds=1)
    assert capture_time(NOW + timedelta(seconds=1), [newest]) == NOW + timedelta(seconds=1)
    assert capture_time(NOW, []) == NOW


def test_an_entry_left_writing_starts_as_unknown() -> None:
    assert on_start(_entry(state=State.WRITING)).state is State.UNKNOWN
    assert on_start(_entry()) == _entry()


def test_the_oldest_due_entry_goes_first_and_a_newer_one_to_its_note_waits() -> None:
    first = _entry(id="a", created=NOW, attempts=1, next_try=NOW + timedelta(seconds=5))
    second = _entry(id="b", created=NOW + timedelta(seconds=1))
    elsewhere = _entry(id="c", created=NOW + timedelta(seconds=2), target="Inbox.md")
    assert due([second, first, elsewhere], NOW) == elsewhere
    assert due([second, first], NOW + timedelta(seconds=5)) == first
    assert due([replace(first, state=State.FAILED), second], NOW) == second
    assert due([replace(first, state=State.WRITING), second], NOW) is None
    assert due([], NOW) is None


def test_the_thread_sleeps_until_the_soonest_try() -> None:
    later = NOW + timedelta(minutes=2)
    assert soonest([_entry(next_try=later), _entry(next_try=NOW, state=State.FAILED)]) == later
    assert soonest([]) is None


def test_a_try_reads_first_unless_it_appends_to_the_daily_note_afresh() -> None:
    assert first_step(_entry()) is Step.APPEND
    assert first_step(_entry(state=State.UNKNOWN)) is Step.READ
    assert first_step(_entry(target="Inbox.md")) is Step.READ


NOTE_TEXT = "# Tasks\n- [ ] call Sam  \r\n- [ ] other\n"


@pytest.mark.parametrize(
    ("entry", "step", "outcome", "checking", "expected"),
    [
        # the check finds the line, or not
        (_entry(), Step.READ, Answered(NOTE_TEXT), True, Written()),
        (_entry(), Step.READ, Answered("- [ ] call Sam later"), True, Call(Step.APPEND)),
        # a pending entry's read only says the note exists: the same line twice is two captures
        (_entry(target="Inbox.md"), Step.READ, Answered(NOTE_TEXT), False, Call(Step.APPEND)),
        (
            _entry(target="Inbox.md"),
            Step.READ,
            Refused("not found", missing=True),
            False,
            Call(Step.CREATE),
        ),
        (_entry(), Step.READ, Refused("not found", missing=True), True, Call(Step.APPEND)),
        (_entry(target="Inbox.md"), Step.CREATE, Answered(""), False, Call(Step.APPEND)),
        (_entry(), Step.APPEND, Answered(""), False, Written()),
        # failures
        (
            _entry(),
            Step.APPEND,
            Refused("closed"),
            False,
            Missed("append: closed", uncertain=False),
        ),
        (_entry(), Step.READ, Refused("busy"), True, Missed("read: busy", uncertain=True)),
        (_entry(), Step.READ, Refused("busy"), False, Missed("read: busy", uncertain=False)),
        (
            _entry(),
            Step.APPEND,
            TimedOut(5.0),
            False,
            Missed("append: Obsidian did not answer within 5.0 s", uncertain=True),
        ),
        (
            _entry(),
            Step.READ,
            TimedOut(5.0),
            True,
            Missed("read: Obsidian did not answer within 5.0 s", uncertain=True),
        ),
    ],
)
def test_each_outcome_leads_to_the_next_call_or_ends_the_try(
    entry: Entry,
    step: Step,
    outcome: Answered | Refused | TimedOut,
    checking: bool,
    expected: object,
) -> None:
    assert advance(entry, step, outcome, checking=checking) == expected


def test_failed_tries_back_off_then_fail_on_the_fifth() -> None:
    entry = writing(_entry())
    waits = []
    for _ in range(4):
        entry = missed(entry, Missed("closed", uncertain=False), NOW)
        assert entry.state is State.PENDING
        assert entry.next_try is not None
        waits.append(entry.next_try - NOW)
    assert waits == [
        timedelta(seconds=5),
        timedelta(seconds=30),
        timedelta(minutes=2),
        timedelta(minutes=10),
    ]
    entry = missed(entry, Missed("closed", uncertain=False), NOW)
    assert (entry.state, entry.attempts, entry.next_try, entry.last_error) == (
        State.FAILED,
        5,
        None,
        "closed",
    )


def test_an_uncertain_try_leaves_the_entry_unknown_and_counts() -> None:
    entry = missed(writing(_entry()), Missed("killed", uncertain=True), NOW)
    assert (entry.state, entry.attempts) == (State.UNKNOWN, 1)
    entry = missed(replace(entry, attempts=4), Missed("killed", uncertain=True), NOW)
    assert entry.state is State.FAILED


def test_retry_starts_afresh_and_an_unknown_entry_is_still_checked_first() -> None:
    later = NOW + timedelta(hours=1)
    failed = _entry(state=State.FAILED, attempts=5, last_error="x", next_try=None)
    assert retried(failed, later) == _entry(next_try=later)
    assert retried(_entry(state=State.UNKNOWN, attempts=2), later).state is State.UNKNOWN


def test_copy_gives_the_line_or_for_an_open_capture_the_target() -> None:
    assert copied(_entry()) == "- [ ] call Sam"
    assert copied(_entry(kind=CaptureKind.OPEN, target="People/Sam.md")) == "People/Sam.md"


def test_a_line_is_held_only_as_a_whole_line() -> None:
    assert holds_line("a\n- [ ] x\n", "- [ ] x")
    assert holds_line("- [ ] x  ", "- [ ] x")
    assert not holds_line("- [ ] x and more", "- [ ] x")
    assert not holds_line("", "- [ ] x")
