"""The pure half of reporting the outbox as a task (decision 12).

A *burst* starts when the outbox goes from empty to non-empty and ends when it is empty
again. Its only counter is ``written``: the entries the thread wrote in it. The total is
``written`` plus the entries still in the outbox, so a capture made mid-burst raises the
total, and a discarded one leaves it. ``task_for`` says what the host should be told, from
the outbox's entries, that counter, whether the thread is waiting for Obsidian, and the task
last reported; ``None`` means tell it nothing.
"""

from collections.abc import Iterable

from cmd_sdk import Task

from vault.outbox import Entry, State, age

TASK_ID = "outbox"
LABEL = "Vault captures"
WAITING = "waiting for Obsidian"


def task_for(
    entries: Iterable[Entry], written: int, *, blocked: bool, last: Task | None
) -> Task | None:
    """The task to report now, or ``None`` to report nothing.

    - Any entry ``failed``: ``failed``, with the oldest such entry's error and the count
      stuck at ``written`` of the total. A failure outranks work still going on.
    - Otherwise entries remain: ``running``, ``written`` of the total. The detail is
      "waiting for Obsidian" when ``blocked``, else the entry in hand (the one being
      written, else the oldest) and, if its last try failed, why it will be tried again.
    - Otherwise the outbox is empty: ``done`` after writes; after nothing written, ``done``
      too if the host was last told something other than ``done`` (a failed capture was
      discarded, and its task must go), else ``None``.
    """
    pending = sorted(entries, key=age)
    total = written + len(pending)
    failed = [entry for entry in pending if entry.state is State.FAILED]
    if failed:
        reason = _first_line(failed[0].last_error) or "could not be written"
        return Task(
            TASK_ID, LABEL, "failed", written, total, f"{len(failed)} not written: {reason}"
        )
    if pending:
        return Task(TASK_ID, LABEL, "running", written, total, _detail(pending, blocked=blocked))
    if written:
        return Task(TASK_ID, LABEL, "done", written, written, f"{written} written")
    if last is not None and last.state != "done":
        return Task(TASK_ID, LABEL, "done", detail="nothing left to write")
    return None


def next_written(written: int, entries: Iterable[Entry]) -> int:
    """The counter after looking at the outbox: back to 0 once it is empty."""
    return written if any(True for _ in entries) else 0


def _detail(pending: list[Entry], *, blocked: bool) -> str:
    if blocked:
        return WAITING
    current = next((entry for entry in pending if entry.state is State.WRITING), pending[0])
    detail = _first_line(current.line)
    reason = _first_line(current.last_error)
    return f"{detail} (retrying: {reason})" if reason else detail


def _first_line(text: str | None) -> str:
    lines = (text or "").strip().splitlines()
    return lines[0].strip() if lines else ""
