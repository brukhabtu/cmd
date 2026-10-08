"""The outbox thread: the only code that calls the CLI to write.

Decision 10. It takes the oldest due entry, one at a time, and only while Obsidian runs, so
a closed Obsidian costs no tries. Before a try it writes the entry as ``writing``; after it,
it deletes the entry (written) or writes the outcome (tried again later, or failed). It
sleeps until ``run`` queues an entry or the person presses Retry, until the soonest next
try, or 10 s while an entry waits for Obsidian.
"""

import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from vault.gateway import invoke
from vault.invocations import write_arguments
from vault.outbox import (
    Call,
    Missed,
    State,
    Written,
    advance,
    due,
    first_step,
    missed,
    soonest,
    writing,
)
from vault.schema import Obsidian
from vault.store import Outbox

WAIT_FOR_OBSIDIAN = 10.0
"""Seconds between looks while an entry waits for Obsidian to run."""


@dataclass(frozen=True, slots=True)
class World:
    """What the thread reaches: the CLI's settings, whether Obsidian runs, the time."""

    obsidian: Obsidian
    running: Callable[[], bool]
    clock: Callable[[], datetime]


def step(outbox: Outbox, world: World) -> float | None:
    """Make one try at the oldest due entry, if any, and say how long to sleep after it.

    ``None`` sleeps until woken. Raises only what the outbox's files raise (``OSError``).
    """
    now = world.clock()
    entries = outbox.entries()
    entry = due(entries, now)
    if entry is None:
        later = soonest(entries)
        return None if later is None else max(0.0, (later - now).total_seconds())
    if world.obsidian.bin is None or not world.running():
        return WAIT_FOR_OBSIDIAN
    checking = entry.state is State.UNKNOWN
    if not outbox.update(writing(entry)):
        return 0.0
    current = first_step(entry)
    while True:
        arguments = write_arguments(world.obsidian, entry, current)
        outcome = invoke(arguments, world.obsidian.deadlines.write)
        match advance(entry, current, outcome, checking=checking):
            case Call() as call:
                current = call.step
            case Written():
                outbox.remove(entry.id)
                return 0.0
            case Missed() as miss:
                outbox.update(missed(entry, miss, world.clock()))
                return 0.0


class Worker:
    """The thread, with a way to stop it for tests and an orderly exit."""

    def __init__(self, outbox: Outbox, world: World) -> None:
        self._outbox = outbox
        self._world = world
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="vault-outbox", daemon=True)

    def start(self) -> Worker:
        """Start the thread; returns the worker, to keep."""
        self._thread.start()
        return self

    def stop(self, timeout: float | None = None) -> None:
        """Stop after the try in hand, and wait up to ``timeout`` seconds for it."""
        self._stopped.set()
        self._outbox.wake()
        self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stopped.is_set():
            try:
                wait = step(self._outbox, self._world)
            except Exception as error:  # ruff: ignore[blind-except] - the thread must outlive any failure
                sys.stderr.write(f"vault: the outbox thread: {type(error).__name__}: {error}\n")
                wait = WAIT_FOR_OBSIDIAN
            if not self._stopped.is_set() and (wait is None or wait > 0):
                self._outbox.sleep(wait)
