"""What the plugin remembers between searches: the short cache, the rest, the last call.

Decision 11. Each provider's answer for a text is kept ``CACHE_SECONDS`` (at most
``CACHE_SIZE`` answers), so backspacing over a word and typing it again starts nothing.
Only an answer that came back in time is kept, hits or a failure alike; a call that missed
the deadline, cut or not, is not, and counts toward the rest. A provider whose last
``REST_AFTER`` calls all missed the deadline starts nothing for ``REST_SECONDS``. A call
back in time sets the count to 0; an answer from the cache is no call and changes nothing.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from cmd_sdk.expiry import expired

from search.merge import Called, Report

CACHE_SECONDS = 10.0
CACHE_SIZE = 64
REST_AFTER = 3
REST_SECONDS = 30.0
DETAIL_LINES = 5
"""Lines of stderr that Enter on a problem shows."""


@dataclass(frozen=True, slots=True)
class Last:
    """A provider's last call: the command as run, what came back, stderr's first lines."""

    command: str
    report: Report | None = None
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class _Kept:
    stamp: float
    report: Report


class Memory:
    """The cache, the rest and the last call, behind one lock.

    A class because the providers' threads and ``query`` share it. ``ticks`` is the clock
    the cache and the rest age by, injected so a test moves time.
    """

    def __init__(self, ticks: Callable[[], float] = time.monotonic) -> None:
        self._ticks = ticks
        self._lock = threading.Lock()
        self._kept: dict[tuple[str, str], _Kept] = {}
        self._slow: dict[str, int] = {}
        self._rest_until: dict[str, float] = {}
        self._last: dict[str, Last] = {}

    def cached(self, provider: str, text: str) -> Report | None:
        """The answer kept for this provider and text, if it is fresh."""
        with self._lock:
            kept = self._kept.get((provider, text))
            if kept is None or expired(self._ticks(), kept.stamp, CACHE_SECONDS):
                return None
            return kept.report

    def resting(self, provider: str) -> float | None:
        """Seconds the provider still rests, or ``None`` when it may be called."""
        with self._lock:
            until = self._rest_until.get(provider)
            now = self._ticks()
            if until is None or now >= until:
                return None
            return until - now

    def started(self, provider: str, command: str) -> None:
        """A call is starting: remember its command, for Enter on its problem."""
        with self._lock:
            self._last[provider] = Last(command)

    def record(self, provider: str, text: str, report: Report, stderr: str = "") -> None:
        """A call came back: keep it, or count it toward the rest."""
        now = self._ticks()
        with self._lock:
            last = self._last.get(provider, Last(""))
            lines = "\n".join(stderr.splitlines()[:DETAIL_LINES])
            self._last[provider] = Last(last.command, report, lines)
            if isinstance(report, Called) and report.timed_out:
                self._slow[provider] = self._slow.get(provider, 0) + 1
                if self._slow[provider] >= REST_AFTER:
                    self._rest_until[provider] = now + REST_SECONDS
                return
            self._slow[provider] = 0
            fresh = {
                key: kept
                for key, kept in self._kept.items()
                if not expired(now, kept.stamp, CACHE_SECONDS)
            }
            fresh.pop((provider, text), None)
            fresh[provider, text] = _Kept(now, report)
            self._kept = dict(list(fresh.items())[-CACHE_SIZE:])

    def last(self, provider: str) -> Last | None:
        """The provider's last call since the plugin started, if any."""
        with self._lock:
            return self._last.get(provider)

    def reports(self) -> dict[str, Report]:
        """Each provider's last report, for the status keyword."""
        with self._lock:
            return {
                name: last.report for name, last in self._last.items() if last.report is not None
            }
