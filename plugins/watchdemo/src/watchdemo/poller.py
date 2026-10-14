"""The polling thread: read the tickets file, diff it against the state, tell the host.

The shell around ``diff``. ``Poller.poll`` is one step with its clocks injected, so a test
drives it directly and never sleeps; ``Poller.start`` runs it on a daemon thread.

An unreadable file is one task, ``source``, reported failed once and done once it reads
again (decision 12); a change is one notice (decision 13), or one summary after a long gap.
Nothing here raises into the thread: a failed report is logged.
"""

import json
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from cmd_sdk import InvalidNoticeError, InvalidTaskError, Task, notify, report

from watchdemo.diff import Notice, diff, plan_notices
from watchdemo.keeper import Store
from watchdemo.state import Change, State
from watchdemo.tickets import Ticket, TicketsError, parse_tickets

SOURCE_TASK = "source"
SOURCE_LABEL = "Tickets file"


class SourceError(Exception):
    """The tickets file cannot be used. The message says why, naming the file."""


def read_tickets(path: Path) -> tuple[Ticket, ...]:
    """The tickets in the file at ``path`` (``~`` is the home directory).

    Raises:
        SourceError: The file is missing or unreadable, is not JSON, or is not a list of
            tickets.
    """
    path = path.expanduser()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise SourceError(f"{path} does not exist") from None
    except (OSError, UnicodeDecodeError) as error:
        raise SourceError(f"{path} cannot be read: {error}") from error
    try:
        return parse_tickets(json.loads(text))
    except json.JSONDecodeError as error:
        raise SourceError(f"{path} is not valid JSON: {error}") from error
    except TicketsError as error:
        raise SourceError(f"{path}: {error}") from error


def local_time() -> str:
    """The local time to the second, as a change records it."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")  # ruff: ignore[call-datetime-now-without-tzinfo] - shown to the person as their own clock


class Poller:
    """Reads the file every ``interval`` seconds and tells the host what moved.

    ``clock`` (a monotonic reading in seconds) and ``wall`` (the text a change records as
    its time) are read once per poll; a test passes its own.
    """

    def __init__(
        self,
        path: Path,
        interval: float,
        store: Store,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], str] = local_time,
    ) -> None:
        self._path = path
        self._interval = interval
        self._store = store
        self._clock = clock
        self._wall = wall
        self._last: float | None = None
        self._failing = False

    def start(self) -> threading.Event:
        """Start the daemon thread. Set the returned event to stop it after the poll in hand."""
        stop = threading.Event()
        threading.Thread(
            target=self._loop, args=(stop,), name="watchdemo-poll", daemon=True
        ).start()
        return stop

    def _loop(self, stop: threading.Event) -> None:
        while not stop.is_set():
            self.poll()
            stop.wait(self._interval)

    def poll(self) -> None:
        """Read the file once and act on it. Never raises."""
        try:
            self._poll()
        except Exception as error:  # ruff: ignore[blind-except] - the thread must outlive any failure
            sys.stderr.write(f"watchdemo: the poll: {type(error).__name__}: {error}\n")

    def _poll(self) -> None:
        now = self._clock()
        slept = 0.0 if self._last is None else now - self._last
        self._last = now
        try:
            tickets = read_tickets(self._path)
        except SourceError as error:
            self._fail(str(error))
            return
        self._recover()
        at = self._wall()
        found = self._store.transact(lambda state: _apply(state, tickets, at))
        for notice in plan_notices(found, tickets, slept, self._interval):
            _tell(notice)

    def _fail(self, reason: str) -> None:
        if self._failing:
            return
        self._failing = True
        _send(Task(SOURCE_TASK, SOURCE_LABEL, "failed", detail=reason))

    def _recover(self) -> None:
        if not self._failing:
            return
        self._failing = False
        _send(Task(SOURCE_TASK, SOURCE_LABEL, "done"))


def _apply(state: State, tickets: tuple[Ticket, ...], at: str) -> tuple[State, tuple[Change, ...]]:
    result = diff(state, tickets, at)
    return result.state, result.changes


def _send(task: Task) -> None:
    try:
        report(task)
    except InvalidTaskError as error:
        sys.stderr.write(f"watchdemo: cannot report {task.id}: {error}\n")


def _tell(notice: Notice) -> None:
    try:
        notify(notice.id, notice.title, notice.body, notice.open)
    except InvalidNoticeError as error:
        sys.stderr.write(f"watchdemo: cannot notify about {notice.id}: {error}\n")
