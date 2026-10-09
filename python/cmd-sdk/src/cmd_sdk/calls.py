"""Run a program with a deadline, keep what it said, and leave a slow one to finish."""

import contextlib
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import IO

_DRAIN_GRACE = 1.0
"""Seconds to wait, after the child exits, for the rest of its output to be read."""

_CHUNK = 65536


@dataclass(frozen=True, slots=True)
class CallResult:
    """What a call left behind.

    ``returncode`` is ``None`` when the deadline passed before the child exited.
    ``stdout`` and ``stderr`` hold what had been written by then (raw bytes), so a slow
    search still gives the paths it found. ``truncated`` is true when ``max_output`` was
    reached on either stream: the child was killed and what is held is the first
    ``max_output`` bytes.
    """

    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    truncated: bool = False


class _Collector:
    """Reads one pipe to its end on a daemon thread, keeping what it reads up to a cap.

    Past the cap it keeps nothing more, tells ``on_overflow`` once, and goes on reading to
    the end so that a child being killed is never blocked on a full pipe.
    """

    def __init__(self, stream: IO[bytes], cap: int | None, on_overflow: Callable[[], None]) -> None:
        self._stream = stream
        self._cap = cap
        self._on_overflow = on_overflow
        self._chunks: list[bytes] = []
        self._kept = 0
        self._lock = threading.Lock()
        self.overflowed = False
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        with self._stream:
            while chunk := self._stream.read(_CHUNK):
                self._keep(chunk)

    def _keep(self, chunk: bytes) -> None:
        with self._lock:
            room = chunk if self._cap is None else chunk[: max(0, self._cap - self._kept)]
            self._chunks.append(room)
            self._kept += len(room)
            first_overflow = len(room) < len(chunk) and not self.overflowed
            self.overflowed = self.overflowed or len(room) < len(chunk)
        if first_overflow:
            self._on_overflow()

    def so_far(self) -> bytes:
        with self._lock:
            return b"".join(self._chunks)


def call(
    command: Sequence[str],
    timeout: float,
    *,
    kill_on_timeout: bool = False,
    keep_stdout: bool = True,
    max_output: int | None = None,
) -> CallResult:
    """Run ``command`` and wait up to ``timeout`` seconds for it.

    ``command`` is a list, never a string, and no shell is involved. The child's stdout and
    stderr are always captured, never inherited: a child that inherited file descriptor 1
    would write into the plugin's protocol stream (``serve`` repoints ``sys.stdout``, not
    the descriptor). Its stdin is closed, so it cannot read the protocol's requests either.

    When the deadline passes the call does not wait for the child: the result says
    ``timed_out`` and holds the output so far. The child carries on in a session of its
    own, with daemon threads draining its pipes and reaping it, unless ``kill_on_timeout``
    is set, which kills it and whatever it started: right for a search that nobody wants
    the rest of, wrong for a command whose work should finish. With ``kill_on_timeout`` a
    child that exited but left a grandchild holding its pipes open past the grace is cleaned
    up the same way. Starting the program can fail with ``OSError``, which is raised as is.

    ``max_output`` caps each stream, in bytes: the first ``max_output`` bytes are kept, the
    child is killed with whatever it started, and the result says ``truncated``. Without it
    everything the child writes before the deadline is held in memory.

    ``keep_stdout=False`` sends the child's stdout to ``/dev/null`` instead of a pipe, for a
    command left to finish whose output nobody reads: a pipe nobody drains would hold it in
    memory, and would end it with SIGPIPE when the plugin exits. It is still never inherited.

    Raises:
        TypeError: ``command`` is a string.
        RuntimeError: the child came without its pipes (it cannot happen).
    """
    if isinstance(command, str):
        raise TypeError("command is a list of arguments, not a string")
    process = subprocess.Popen(
        list(command),
        bufsize=0,  # raw pipes: a read returns what has arrived instead of waiting to fill
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if keep_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if process.stderr is None or (keep_stdout and process.stdout is None):  # pragma: no cover
        raise RuntimeError("the child has no pipes")

    def stop() -> None:
        # The child leads its own session, so its process group is it and its children.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)

    out = _Collector(process.stdout, max_output, stop) if process.stdout is not None else None
    err = _Collector(process.stderr, max_output, stop)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if kill_on_timeout:
            stop()
        # Someone has to wait for it, or it lingers as a zombie as long as the plugin lives.
        threading.Thread(target=process.wait, daemon=True).start()
        return CallResult(None, _kept(out), err.so_far(), timed_out=True, truncated=_over(out, err))
    # One grace for both pipes: a grandchild holding them open costs it once, not twice.
    deadline = time.monotonic() + _DRAIN_GRACE
    for collector in (out, err):
        if collector is not None:
            collector.thread.join(max(0.0, deadline - time.monotonic()))
    if kill_on_timeout and any(c is not None and c.thread.is_alive() for c in (out, err)):
        stop()  # a grandchild still holds the pipes: the grace is over
    return CallResult(
        process.returncode, _kept(out), err.so_far(), timed_out=False, truncated=_over(out, err)
    )


def _over(out: _Collector | None, err: _Collector) -> bool:
    return err.overflowed or (out is not None and out.overflowed)


def _kept(collector: _Collector | None) -> bytes:
    return collector.so_far() if collector is not None else b""
