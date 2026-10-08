"""The shell's edge with the world: calls to the obsidian CLI and the probe, and their caches.

Every call goes through the SDK's ``call`` with ``kill_on_timeout``, so a call killed at its
deadline takes what it started with it. A call's answer comes back as an ``Outcome`` value,
never an exception: a missing or broken ``obsidian.bin`` (``OSError``) is a refusal too.
"""

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cmd_sdk import call
from cmd_sdk.expiry import expired

from vault.invocations import first_line, probe_arguments, says_missing
from vault.outbox import Answered, Outcome, Refused, TimedOut

PROBE_TTL = 2.0
"""Seconds the probe's answer is kept."""

SEARCH_TTL = 10.0
"""Seconds a search's answer is kept, per text."""


def invoke(arguments: Sequence[str], deadline: float) -> Outcome:
    """Run the CLI with these arguments and say how it went."""
    try:
        result = call(arguments, deadline, kill_on_timeout=True)
    except OSError as error:
        return Refused(f"cannot run {arguments[0]}: {error.strerror or error}")
    if result.timed_out:
        return TimedOut(deadline)
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0:
        fallback = f"the CLI exited with {result.returncode}"
        return Refused(first_line(stderr, fallback), missing=says_missing(stderr))
    return Answered(result.stdout.decode("utf-8", errors="replace"))


def probe(process: str, deadline: float) -> bool:
    """Whether a process of exactly this name runs: ``pgrep -x``, exit 0 [2.4]."""
    try:
        result = call(probe_arguments(process), deadline, kill_on_timeout=True)
    except OSError:
        return False
    return result.returncode == 0


class Running:
    """Whether Obsidian runs, asked at most once every ``PROBE_TTL`` seconds.

    The query path and the thread share it. ``ask`` is the probe, injected so a test needs
    no Obsidian; a class because the answer and its age change together under a lock.
    """

    def __init__(
        self, ask: Callable[[], bool], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ask = ask
        self._clock = clock
        self._lock = threading.Lock()
        self._stamp: float | None = None
        self._value = False

    def __call__(self) -> bool:
        """The last answer if it is fresh, or a new one."""
        with self._lock:
            if not expired(self._clock(), self._stamp, PROBE_TTL):
                return self._value
        value = self._ask()
        with self._lock:
            self._value = value
            self._stamp = self._clock()
        return value


@dataclass(frozen=True, slots=True)
class _Kept:
    stamp: float
    paths: tuple[str, ...]


class Searches:
    """What each search answered, kept ``SEARCH_TTL`` seconds per text."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._kept: dict[tuple[str, str], _Kept] = {}

    def get(self, key: tuple[str, str]) -> tuple[str, ...] | None:
        """The paths a fresh answer holds, or ``None``."""
        with self._lock:
            kept = self._kept.get(key)
            if kept is None or expired(self._clock(), kept.stamp, SEARCH_TTL):
                return None
            return kept.paths

    def put(self, key: tuple[str, str], paths: tuple[str, ...]) -> None:
        """Keep an answer, and forget the stale ones."""
        now = self._clock()
        with self._lock:
            self._kept = {
                old: kept
                for old, kept in self._kept.items()
                if not expired(now, kept.stamp, SEARCH_TTL)
            }
            self._kept[key] = _Kept(now, paths)
