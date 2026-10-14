from dataclasses import replace
from datetime import UTC, datetime, timedelta

from cmd_sdk import Task
from vault.outbox import Entry, State
from vault.progress import LABEL, TASK_ID, WAITING, next_written, task_for
from vault.schema import CaptureKind

NOW = datetime(2026, 10, 8, 14, 30, 5, tzinfo=UTC)


def entry(
    name: str = "a",
    state: State = State.PENDING,
    *,
    line: str = "- [ ] call Sam",
    error: str | None = None,
    minutes: int = 0,
) -> Entry:
    return Entry(
        id=name,
        created=NOW + timedelta(minutes=minutes),
        keyword="todo",
        kind=CaptureKind.APPEND,
        target="@daily",
        template=None,
        heading=None,
        line=line,
        state=state,
        last_error=error,
    )


def running(done: int, total: int, detail: str) -> Task:
    return Task(TASK_ID, LABEL, "running", done, total, detail)


# --- nothing to say -------------------------------------------------------------------------


def test_an_empty_outbox_that_was_never_reported_says_nothing() -> None:
    assert task_for([], 0, blocked=False, last=None) is None


def test_an_empty_outbox_after_a_done_report_says_nothing_again() -> None:
    last = Task(TASK_ID, LABEL, "done", 2, 2)
    assert task_for([], 0, blocked=False, last=last) is None


# --- running -------------------------------------------------------------------------------


def test_waiting_entries_run_with_nothing_written_and_the_oldest_as_detail() -> None:
    entries = [entry("b", minutes=1, line="- second"), entry("a", line="- first")]
    assert task_for(entries, 0, blocked=False, last=None) == running(0, 2, "- first")


def test_the_entry_being_written_is_the_detail_even_when_older_ones_wait() -> None:
    entries = [entry("a", line="- first"), entry("b", State.WRITING, minutes=1, line="- second")]
    assert task_for(entries, 0, blocked=False, last=None) == running(0, 2, "- second")


def test_written_entries_count_towards_done_and_total() -> None:
    assert task_for([entry("c")], 2, blocked=False, last=None) == running(2, 3, "- [ ] call Sam")


def test_a_closed_obsidian_is_running_with_the_waiting_detail_not_a_failure() -> None:
    entries = [entry("a", error="append: boom"), entry("b", State.UNKNOWN, minutes=1)]
    assert task_for(entries, 1, blocked=True, last=None) == running(1, 3, WAITING)


def test_a_failed_try_that_will_be_retried_says_why_in_the_detail() -> None:
    task = task_for([entry(error="append: Error: slow\nmore")], 0, blocked=False, last=None)
    assert task == running(0, 1, "- [ ] call Sam (retrying: append: Error: slow)")


def test_an_unknown_entry_is_running_not_failed() -> None:
    task = task_for([entry(state=State.UNKNOWN)], 0, blocked=False, last=None)
    assert task is not None
    assert task.state == "running"


def test_only_the_first_line_of_the_entry_is_the_detail() -> None:
    task = task_for([entry(line="- first\nsecond")], 0, blocked=False, last=None)
    assert task is not None
    assert task.detail == "- first"


# --- failed --------------------------------------------------------------------------------


def test_a_failed_entry_fails_the_task_with_the_reason_and_the_count_stuck() -> None:
    entries = [entry("a", State.FAILED, error="append: Error: something went wrong\nx")]
    assert task_for(entries, 3, blocked=False, last=None) == Task(
        TASK_ID, LABEL, "failed", 3, 4, "1 not written: append: Error: something went wrong"
    )


def test_a_failure_outranks_entries_still_going_and_a_closed_obsidian() -> None:
    entries = [
        entry("a", State.FAILED, error="old", minutes=0),
        entry("b", State.FAILED, error="newer", minutes=1),
        entry("c", minutes=2),
    ]
    assert task_for(entries, 0, blocked=True, last=None) == Task(
        TASK_ID, LABEL, "failed", 0, 3, "2 not written: old"
    )


def test_a_failed_entry_without_an_error_still_gives_a_reason() -> None:
    task = task_for([entry(state=State.FAILED)], 0, blocked=False, last=None)
    assert task is not None
    assert task.detail == "1 not written: could not be written"


# --- done ----------------------------------------------------------------------------------


def test_an_outbox_emptied_by_writes_is_done_with_the_count() -> None:
    assert task_for([], 3, blocked=False, last=running(2, 3, "x")) == Task(
        TASK_ID, LABEL, "done", 3, 3, "3 written"
    )


def test_a_failed_capture_that_is_discarded_clears_the_failed_task() -> None:
    last = Task(TASK_ID, LABEL, "failed", 0, 1, "1 not written: x")
    assert task_for([], 0, blocked=False, last=last) == Task(
        TASK_ID, LABEL, "done", detail="nothing left to write"
    )


def test_a_running_capture_that_is_discarded_clears_the_running_task() -> None:
    task = task_for([], 0, blocked=True, last=running(0, 1, WAITING))
    assert task is not None
    assert task.state == "done"
    assert task.done is None
    assert task.total is None


def test_every_task_has_the_one_id_and_label_and_a_valid_progress() -> None:
    cases = [
        task_for([entry()], 0, blocked=False, last=None),
        task_for([entry(state=State.FAILED)], 2, blocked=False, last=None),
        task_for([], 2, blocked=False, last=None),
    ]
    for task in cases:
        assert task is not None
        assert (task.id, task.label) == ("outbox", "Vault captures")
        assert task.done is not None
        assert task.total is not None
        assert task.done <= task.total


# --- the counter ---------------------------------------------------------------------------


def test_the_counter_resets_only_when_the_outbox_is_empty() -> None:
    assert next_written(4, [entry()]) == 4
    assert next_written(4, [replace(entry(), state=State.FAILED)]) == 4
    assert next_written(4, []) == 0
    assert next_written(0, []) == 0
