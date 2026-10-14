"""The shell around task reports and notices: one lock for everything written to the stream.

``serve`` writes answers from its own thread and a plugin's background threads call
``report`` and ``notify``; all write under the one lock here, so lines never interleave
(decisions 12 and 13).
"""

import contextlib
import threading
import time
from collections.abc import Callable, Generator
from typing import TextIO

from cmd_sdk.notices import CAPABILITY as NOTIFY
from cmd_sdk.notices import encode_event as encode_notice
from cmd_sdk.protocol import BEFORE_DESCRIBE, Agreement
from cmd_sdk.tasks import CAPABILITY, Task, Throttle, encode_event


class Reporter:
    """Owns writes to the protocol stream, for answers, task reports and notices.

    ``clock`` is read for the throttle only; a test passes its own.
    """

    def __init__(self, sink: TextIO, clock: Callable[[], float] = time.monotonic) -> None:
        self._sink = sink
        self._lock = threading.Lock()
        self._agreement = BEFORE_DESCRIBE
        self._throttle = Throttle(clock)

    def agree(self, agreement: Agreement) -> None:
        """Record what ``describe`` agreed, so ``report`` knows whether the host reads tasks."""
        with self._lock:
            self._agreement = agreement

    def write(self, line: str) -> None:
        """Write one line of the protocol and flush it, under the lock."""
        with self._lock:
            self._sink.write(line)
            self._sink.flush()

    def report(self, task: Task) -> None:
        """Send this task to the host, if the host reads tasks and the throttle allows.

        The task is checked either way, so a mistake shows up whatever the host is. A write
        to a stream the host has closed is dropped: there is nobody to tell. A task the
        protocol cannot carry raises ``InvalidTaskError`` and writes nothing.
        """
        line = encode_event(task)
        with self._lock:
            if CAPABILITY not in self._agreement.capabilities or not self._throttle.allow(task):
                return
            with contextlib.suppress(OSError, ValueError):
                self._sink.write(line)
                self._sink.flush()

    def notify(
        self,
        id: str,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
        title: str,
        body: str | None = None,
        open: str | None = None,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
    ) -> None:
        """Send this notice to the host, if the host reads notices.

        The notice is checked either way, so a mistake shows up whatever the host is. A write
        to a stream the host has closed is dropped. A notice the protocol cannot carry raises
        ``InvalidNoticeError`` and writes nothing. There is no throttle here: the plugin sends
        one notice per change, and the host drops what is above its rate.
        """
        line = encode_notice(id, title, body, open)
        with self._lock:
            if NOTIFY not in self._agreement.capabilities:
                return
            with contextlib.suppress(OSError, ValueError):
                self._sink.write(line)
                self._sink.flush()


_active: Reporter | None = None


@contextlib.contextmanager
def installed(reporter: Reporter) -> Generator[None]:
    """Make ``report`` write through this reporter while the block runs."""
    global _active  # ruff: ignore[global-statement] - the one stream a process speaks on
    previous, _active = _active, reporter
    try:
        yield
    finally:
        _active = previous


def report(task: Task) -> None:
    """Report a background task to the host. Call it from any thread.

    The latest report per ``task.id`` is what the host shows. It does nothing, quietly,
    before ``serve`` has had a ``describe`` from the host, or when the host did not name
    the ``tasks`` capability: a plugin reports unconditionally and the SDK stays silent
    where the host would not read it. A ``running`` report of a task is sent at most twice
    a second; a change of state is always sent.

    A task the protocol cannot carry raises ``InvalidTaskError`` to the caller, whatever the
    host is, and nothing is written: ``task`` is not a ``Task``, a text is not text, ``state``
    is not ``running``, ``done`` or ``failed``, ``done`` is above ``total``, or only one of
    ``done`` and ``total`` is given.
    """
    reporter = _active
    if reporter is None:
        encode_event(task)
        return
    reporter.report(task)


def notify(
    id: str,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
    title: str,
    body: str | None = None,
    open: str | None = None,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
) -> None:
    """Tell the person something. Call it from any thread.

    ``id`` names the thing within your plugin, and a later notice with the same ``id``
    replaces the earlier one in the host's list of recent notices. ``title`` is required;
    ``body`` is a second line; ``open`` is a target (a URL or a path) the host opens when the
    person chooses the notice. The host cuts ``title`` and ``body`` at 160 characters and
    drops control characters.

    It does nothing, quietly, before ``serve`` has had a ``describe`` from the host, or when
    the host did not name the ``notify`` capability, so call it unconditionally. Send one
    notice per change, and one summary after a wake with many: the SDK does not throttle, and
    the host drops a plugin's notices above 5 in 10 seconds.

    A notice the protocol cannot carry raises ``InvalidNoticeError`` to the caller, whatever
    the host is, and nothing is written: ``id`` or ``title`` is not text or is empty, or
    ``body`` or ``open`` is given and is not text, or ``open`` is empty.
    """
    reporter = _active
    if reporter is None:
        encode_notice(id, title, body, open)
        return
    reporter.notify(id, title, body, open)
