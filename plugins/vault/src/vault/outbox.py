"""The pure half of the outbox: an entry, its states, and what each call's outcome does to it.

Decision 10. Every capture becomes an entry before anything is written; the plugin's thread
writes it through the CLI and deletes it only when the CLI said it was written, or a check
found its line in the note. Time enters as ``now``, randomness as ``suffix``, and the CLI's
answers as ``Outcome`` values, so every rule here is tested with plain data.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, assert_never

from vault.schema import DAILY, Capture, CaptureKind, safe_in_path

MAX_TRIES = 5
"""The fifth failed try makes an entry ``failed``."""

BACKOFF = (
    timedelta(seconds=5),
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
)
"""How long after the first, second, third and fourth failed try the next one comes."""


class State(StrEnum):
    """Where an entry is. ``gone`` has no value: a gone entry's file is deleted."""

    PENDING = "pending"
    WRITING = "writing"
    UNKNOWN = "unknown"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Entry:
    """One capture waiting to be written. Its file holds exactly these fields."""

    id: str
    created: datetime
    keyword: str
    kind: CaptureKind
    target: str
    template: str | None
    heading: str | None
    line: str
    state: State = State.PENDING
    attempts: int = 0
    next_try: datetime | None = None
    last_error: str | None = None
    open_until: datetime | None = None


class EntryError(ValueError):
    """An entry's JSON is not an entry. The message says which field."""


def render(
    capture: Capture, text: str, now: datetime, date_format: str, time_format: str
) -> tuple[str, str]:
    """The line and the target of a capture of ``text`` made at ``now``.

    Rendered once, when queued, so every try writes exactly the same text. A newline in the
    text becomes a space: the line is one line.
    """
    flat = " ".join(text.split())
    date = now.strftime(date_format)
    line = capture.line.format(text=flat, date=date, time=now.strftime(time_format))
    target = capture.target
    if target != DAILY:
        target = target.format(text=safe_in_path(flat), date=date)
    return line, target


def new_entry(
    capture: Capture,
    text: str,
    now: datetime,
    suffix: str,
    formats: tuple[str, str],
) -> Entry:
    """The entry for a capture made at ``now``; ``suffix`` is six random hex digits.

    The id is the local capture time and the suffix, so ids sort oldest first.
    """
    line, target = render(capture, text, now, *formats)
    return Entry(
        id=f"{now.strftime('%Y%m%dT%H%M%S')}-{suffix}",
        created=now,
        keyword=capture.keyword,
        kind=capture.kind,
        target=target,
        template=capture.template,
        heading=capture.heading,
        line=line,
        next_try=now,
    )


def capture_time(now: datetime, entries: Iterable[Entry]) -> datetime:
    """The time a new capture records: ``now``, or just after the newest entry's.

    Two captures in one instant would otherwise be ordered by their random suffixes, and
    the order captures are made in is the order they are written.
    """
    newest = max((entry.created for entry in entries), default=None)
    if newest is not None and now <= newest:
        return newest + timedelta(microseconds=1)
    return now


def on_start(entry: Entry) -> Entry:
    """An entry as the plugin finds it at start: one left ``writing`` may have landed."""
    if entry.state is State.WRITING:
        return replace(entry, state=State.UNKNOWN)
    return entry


def due(entries: Iterable[Entry], now: datetime) -> Entry | None:
    """The oldest entry whose try is due, or ``None``.

    An entry waits while an older one for the same target is still to be written, so two
    captures into one note land in the order they were made. A failed entry holds nothing
    up: it waits for the person.
    """
    waiting: set[str] = set()
    for entry in sorted(entries, key=age):
        if entry.state is State.FAILED:
            continue
        if entry.target not in waiting and _is_due(entry, now):
            return entry
        waiting.add(entry.target)
    return None


def age(entry: Entry) -> tuple[datetime, str]:
    """The order entries were made in: by capture time, then by id within one instant."""
    return (entry.created, entry.id)


def soonest(entries: Iterable[Entry]) -> datetime | None:
    """When the next try falls due, for the thread to sleep until; ``None`` if nothing waits."""
    times = [
        entry.next_try
        for entry in entries
        if entry.state in {State.PENDING, State.UNKNOWN} and entry.next_try is not None
    ]
    return min(times, default=None)


def _is_due(entry: Entry, now: datetime) -> bool:
    if entry.state not in {State.PENDING, State.UNKNOWN}:
        return False
    return entry.next_try is None or entry.next_try <= now


# --- one try ------------------------------------------------------------------------------


class Step(StrEnum):
    """A call to the CLI that a try makes."""

    READ = "read"
    """Read the target: does it exist, and does it hold the line already?"""
    CREATE = "create"
    """Create the target, from the template when there is one."""
    APPEND = "append"
    """Add the line to the target."""


@dataclass(frozen=True, slots=True)
class Answered:
    """The CLI exited 0 and printed ``stdout``."""

    stdout: str


@dataclass(frozen=True, slots=True)
class Refused:
    """The CLI exited non-zero, or could not be started; ``error`` says why."""

    error: str
    missing: bool = False
    """Whether the error says the note does not exist."""


@dataclass(frozen=True, slots=True)
class TimedOut:
    """The call was killed at its deadline: what it did is not known."""

    seconds: float


type Outcome = Answered | Refused | TimedOut


@dataclass(frozen=True, slots=True)
class Call:
    """Make this call next."""

    step: Step


@dataclass(frozen=True, slots=True)
class Written:
    """The line is in the note: delete the entry."""


@dataclass(frozen=True, slots=True)
class Missed:
    """This try failed. ``uncertain`` when the write may have landed."""

    error: str
    uncertain: bool


type Next = Call | Written | Missed


def first_step(entry: Entry) -> Step:
    """The first call of a try.

    A try starts by reading the target when the write may already have landed (the entry
    is ``unknown``), or when the target is a path, since a missing note must be created
    first and the CLI is never asked to create a note that exists [2.4]. ``@daily`` needs no
    read for a fresh entry: ``daily:append`` makes the daily note [2.4].
    """
    if entry.state is State.UNKNOWN or entry.target != DAILY:
        return Step.READ
    return Step.APPEND


def advance(entry: Entry, step: Step, outcome: Outcome, *, checking: bool) -> Next:
    """What follows one call. ``checking`` is whether the try began with the entry ``unknown``.

    A read that answers decides between done, create and append. A read that says the note
    is missing leads to a create, then the append. Any other failure ends the try: a killed
    call, or a failed check, leaves it uncertain whether the line landed.
    """
    match outcome:
        case Answered():
            return _after_answer(entry, step, outcome.stdout, checking=checking)
        case Refused():
            if step is Step.READ and outcome.missing:
                return Call(Step.APPEND if entry.target == DAILY else Step.CREATE)
            return Missed(
                f"{step.value}: {outcome.error}", uncertain=checking and step is Step.READ
            )
        case TimedOut():
            return Missed(
                f"{step.value}: Obsidian did not answer within {outcome.seconds} s", uncertain=True
            )
        case _ as unreachable:
            assert_never(unreachable)


def _after_answer(entry: Entry, step: Step, stdout: str, *, checking: bool) -> Next:
    match step:
        case Step.READ:
            if checking and holds_line(stdout, entry.line):
                return Written()
            return Call(Step.APPEND)
        case Step.CREATE:
            return Call(Step.APPEND)
        case Step.APPEND:
            return Written()
        case _ as unreachable:
            assert_never(unreachable)


def holds_line(note: str, line: str) -> bool:
    """Whether a note holds ``line`` as a whole line, line endings and trailing spaces aside."""
    wanted = line.rstrip()
    return any(existing.rstrip() == wanted for existing in note.splitlines())


def writing(entry: Entry) -> Entry:
    """The entry as it is written to disk before its first call."""
    return replace(entry, state=State.WRITING)


def missed(entry: Entry, miss: Missed, now: datetime) -> Entry:
    """The entry after a failed try: tried again later, or ``failed`` after the fifth."""
    attempts = entry.attempts + 1
    if attempts >= MAX_TRIES:
        return replace(
            entry, state=State.FAILED, attempts=attempts, next_try=None, last_error=miss.error
        )
    return replace(
        entry,
        state=State.UNKNOWN if miss.uncertain else State.PENDING,
        attempts=attempts,
        next_try=now + BACKOFF[attempts - 1],
        last_error=miss.error,
    )


def retried(entry: Entry, now: datetime) -> Entry:
    """Retry: tries afresh, now. An entry whose write may have landed is checked first."""
    state = State.UNKNOWN if entry.state is State.UNKNOWN else State.PENDING
    return replace(entry, state=state, attempts=0, next_try=now, last_error=None)


def copied(entry: Entry) -> str:
    """What Copy puts on the clipboard: the line, or the target's path for ``open``."""
    return entry.target if entry.kind is CaptureKind.OPEN else entry.line


# --- the file -----------------------------------------------------------------------------


def to_json(entry: Entry) -> dict[str, Any]:
    """The entry as its file holds it."""
    return {
        "id": entry.id,
        "created": entry.created.isoformat(),
        "keyword": entry.keyword,
        "kind": entry.kind.value,
        "target": entry.target,
        "template": entry.template,
        "heading": entry.heading,
        "line": entry.line,
        "state": entry.state.value,
        "attempts": entry.attempts,
        "next_try": _stamp(entry.next_try),
        "last_error": entry.last_error,
        "open_until": _stamp(entry.open_until),
    }


def from_json(raw: object) -> Entry:
    """The entry an outbox file holds.

    Raises:
        EntryError: a field is missing or of the wrong kind.
    """
    if not isinstance(raw, Mapping):
        raise EntryError("an entry is a JSON object")
    attempts = raw.get("attempts")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        raise EntryError("attempts: must be a whole number")
    try:
        return Entry(
            id=_required(raw, "id"),
            created=datetime.fromisoformat(_required(raw, "created")),
            keyword=_required(raw, "keyword"),
            kind=CaptureKind(_required(raw, "kind")),
            target=_required(raw, "target"),
            template=_optional(raw, "template"),
            heading=_optional(raw, "heading"),
            line=_required(raw, "line"),
            state=State(_required(raw, "state")),
            attempts=attempts,
            next_try=_time(raw, "next_try"),
            last_error=_optional(raw, "last_error"),
            open_until=_time(raw, "open_until"),
        )
    except ValueError as error:
        raise EntryError(str(error)) from error


def _stamp(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _required(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise EntryError(f"{key}: must be text")
    return value


def _optional(raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise EntryError(f"{key}: must be text or null")
    return value


def _time(raw: Mapping[str, Any], key: str) -> datetime | None:
    value = _optional(raw, key)
    return None if value is None else datetime.fromisoformat(value)
