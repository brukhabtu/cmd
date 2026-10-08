"""Run a program with a deadline, keep what it said, and leave a slow one to finish."""

import subprocess
import threading
from collections.abc import Sequence
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
    search still gives the paths it found.
    """

    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool


class _Collector:
    """Reads one pipe to its end on a daemon thread, keeping everything read so far."""

    def __init__(self, stream: IO[bytes]) -> None:
        self._stream = stream
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        with self._stream:
            while chunk := self._stream.read(_CHUNK):
                with self._lock:
                    self._chunks.append(chunk)

    def so_far(self) -> bytes:
        with self._lock:
            return b"".join(self._chunks)


def call(command: Sequence[str], timeout: float) -> CallResult:
    """Run ``command`` and wait up to ``timeout`` seconds for it.

    ``command`` is a list, never a string, and no shell is involved. The child's stdout and
    stderr are always captured, never inherited: a child that inherited file descriptor 1
    would write into the plugin's protocol stream (``serve`` repoints ``sys.stdout``, not
    the descriptor). Its stdin is closed, so it cannot read the protocol's requests either.

    When the deadline passes the child is not killed and the call does not wait for it:
    the result says ``timed_out``, holds the output so far, and the child carries on in a
    session of its own, with daemon threads draining its pipes and reaping it. Starting
    the program can fail with ``OSError``, which is raised as is.

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if process.stdout is None or process.stderr is None:  # pragma: no cover - PIPE was asked for
        raise RuntimeError("the child has no pipes")
    out = _Collector(process.stdout)
    err = _Collector(process.stderr)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Someone has to wait for it, or it lingers as a zombie as long as the plugin lives.
        threading.Thread(target=process.wait, daemon=True).start()
        return CallResult(None, out.so_far(), err.so_far(), timed_out=True)
    out.thread.join(_DRAIN_GRACE)
    err.thread.join(_DRAIN_GRACE)
    return CallResult(process.returncode, out.so_far(), err.so_far(), timed_out=False)
