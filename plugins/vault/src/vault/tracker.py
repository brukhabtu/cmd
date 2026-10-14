"""The shell of reporting: remembers the burst's counter and what was last reported.

The outbox thread calls ``wrote`` and ``waiting`` as it works and ``refresh`` after each
step; ``refresh`` reports only when ``progress.task_for`` gives a task different from the
last reported. It never raises and never waits on anything but the SDK's write lock: a task
the protocol rejects (``InvalidTaskError``, or anything else) is logged to stderr and
dropped. ``report`` is silent when the host did not name the ``tasks`` capability, so a
plugin with this tracker behaves the same there.
"""

import sys
import threading
from collections.abc import Callable, Iterable

from cmd_sdk import Task, report

from vault.outbox import Entry
from vault.progress import next_written, task_for


class Tracker:
    """Counts the burst and reports the outbox's task when it changes."""

    def __init__(self, send: Callable[[Task], None] = report) -> None:
        self._send = send
        self._lock = threading.Lock()
        self._written = 0
        self._blocked = False
        self._last: Task | None = None

    def wrote(self) -> None:
        """An entry was written."""
        with self._lock:
            self._written += 1

    def waiting(self, *, blocked: bool) -> None:
        """Whether the thread is waiting for Obsidian to run."""
        with self._lock:
            self._blocked = blocked

    def refresh(self, entries: Iterable[Entry]) -> None:
        """Report the task for these entries if it changed. Never raises."""
        try:
            self._refresh(tuple(entries))
        except Exception as error:  # ruff: ignore[blind-except] - reporting must never reach the outbox thread
            sys.stderr.write(f"vault: reporting the outbox: {type(error).__name__}: {error}\n")

    def _refresh(self, entries: tuple[Entry, ...]) -> None:
        with self._lock:
            task = task_for(entries, self._written, blocked=self._blocked, last=self._last)
            self._written = next_written(self._written, entries)
            if task is None or task == self._last:
                return
            self._last = task
        self._send(task)
