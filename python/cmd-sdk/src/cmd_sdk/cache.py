"""A cache of one value, refreshed in the background so a reader never waits."""

import threading
import time
from collections.abc import Callable

from cmd_sdk.expiry import expired


class TtlCache[T]:
    """Holds the last value ``produce`` returned and refreshes it when it gets old.

    ``get`` returns at once with the cached value, or ``None`` before the first fill. When
    the value is older than ``ttl`` seconds, ``get`` starts a refresh on a daemon thread
    and still returns the old value. At most one refresh runs at a time. If ``produce``
    raises, the old value stays and the exception is kept in ``error`` until a refresh
    succeeds; the next attempt waits another ``ttl``, so a broken source is not hammered.

    With ``block_first`` the first ``get`` runs ``produce`` itself and returns its value
    (or ``None`` and ``error`` if it raised). A second thread asking meanwhile does not
    wait; it gets ``None``.

    ``clock`` is injected so a test controls time. ``produce`` runs on another thread, so
    it must not touch anything the caller's thread does.
    """

    def __init__(
        self,
        produce: Callable[[], T],
        ttl: float,
        *,
        block_first: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._produce = produce
        self._ttl = ttl
        self._block_first = block_first
        self._clock = clock
        self._lock = threading.Lock()
        self._value: T | None = None
        self._stamp: float | None = None
        self._error: Exception | None = None
        self._refreshing = False
        self._thread: threading.Thread | None = None

    @property
    def error(self) -> Exception | None:
        """The exception of the last refresh, or ``None`` if it succeeded or none ran."""
        with self._lock:
            return self._error

    def get(self) -> T | None:
        """The cached value, without waiting for a refresh."""
        with self._lock:
            due = not self._refreshing and expired(self._clock(), self._stamp, self._ttl)
            first = self._stamp is None
            if due:
                self._refreshing = True
            value = self._value
        if not due:
            return value
        if first and self._block_first:
            self._refresh()
            with self._lock:
                return self._value
        thread = threading.Thread(target=self._refresh, daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()
        return value

    def wait(self, timeout: float | None = None) -> None:
        """Wait for the background refresh in flight, if any. For tests and orderly shutdown.

        The first fill of a ``block_first`` cache runs on the caller's thread and is not waited for here.
        """
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _refresh(self) -> None:
        try:
            value = self._produce()
        except Exception as error:  # ruff: ignore[blind-except] - any failure is kept for the caller
            with self._lock:
                self._error = error
                self._stamp = self._clock()
                self._refreshing = False
            return
        except BaseException:
            # Not for the caller to keep, but the cache must not wait for it forever.
            with self._lock:
                self._stamp = self._clock()
                self._refreshing = False
            raise
        with self._lock:
            self._value = value
            self._error = None
            self._stamp = self._clock()
            self._refreshing = False
