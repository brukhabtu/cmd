"""What a poll decides: which watched tickets moved, and what the person is told.

Pure: the old state, the tickets just read and the clock's readings go in; the changes, the
new state and the notices come out. The thread and the stream are ``poller``'s.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from watchdemo.state import RECENT_LIMIT, Change, State
from watchdemo.tickets import Ticket

LONG_GAP_FACTOR = 3
"""A poll later than this many intervals after the last means the thread was not running."""

SUMMARY_ABOVE = 3
"""After a long gap, more changes than this are told as one summary."""

SUMMARY_NAMES = 5
"""How many ticket ids the summary names."""


@dataclass(frozen=True, slots=True)
class Diff:
    """The changes a poll found, and the state with them recorded."""

    changes: tuple[Change, ...]
    state: State


@dataclass(frozen=True, slots=True)
class Notice:
    """One call to ``notify``."""

    id: str
    title: str
    body: str | None = None
    open: str | None = None


def diff(state: State, tickets: Sequence[Ticket], at: str) -> Diff:
    """Compare each watched ticket's status with the last seen.

    A watched ticket seen for the first time is recorded and is not a change. One missing
    from the file keeps its last status and is not a change either, so it moves nothing if
    it comes back as it was. The changes are newest first in the state, in file order.
    """
    seen = dict(state.seen)
    changes: list[Change] = []
    for ticket in tickets:
        if ticket.id not in state.watched:
            continue
        before = seen.get(ticket.id)
        if before is not None and before != ticket.status:
            changes.append(Change(ticket.id, ticket.title, before, ticket.status, at))
        seen[ticket.id] = ticket.status
    if not changes and seen == dict(state.seen):
        return Diff((), state)
    recent = (*changes, *state.recent)[:RECENT_LIMIT]
    return Diff(tuple(changes), replace(state, seen=seen, recent=recent))


def long_gap(slept: float, interval: float) -> bool:
    """Whether the thread was away longer than ``LONG_GAP_FACTOR`` intervals."""
    return slept > LONG_GAP_FACTOR * interval


def plan_notices(
    changes: Sequence[Change], tickets: Sequence[Ticket], slept: float, interval: float
) -> tuple[Notice, ...]:
    """The notices for these changes: one each, or one summary after a long gap with many.

    ``slept`` is the time since the last poll, ``interval`` the time between polls. A
    summary replaces the individual notices only when the gap is long (the Mac slept) and
    more than ``SUMMARY_ABOVE`` tickets moved; a burst in one ordinary poll is told one by
    one.
    """
    if long_gap(slept, interval) and len(changes) > SUMMARY_ABOVE:
        names = [change.id for change in changes[:SUMMARY_NAMES]]
        more = len(changes) - len(names)
        body = ", ".join(names) + (f" and {more} more" if more else "")
        return (Notice("summary", f"{len(changes)} tickets moved", body),)
    urls = {ticket.id: ticket.url for ticket in tickets}
    return tuple(
        Notice(
            change.id,
            f"{change.id} moved",
            f"{change.old} -> {change.new}",
            urls.get(change.id),
        )
        for change in changes
    )
