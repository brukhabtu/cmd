"""The outbox on disk and in memory: one JSON file per entry, behind one lock.

Decision 10. A file is written whole under a temporary name, flushed with fsync and renamed,
so an entry is all there or not there. Every change reaches the file before the memory, and
before the call it announces, so the files are the truth at start. ``query`` reads the
entries, ``run`` and the thread change them, and the thread sleeps here until it is woken.
"""

import contextlib
import json
import os
import threading
from collections.abc import Iterable
from pathlib import Path

from vault.outbox import Entry, State, from_json, on_start, to_json


class BusyError(RuntimeError):
    """The entry is being written right now, so it cannot be changed."""


class Outbox:
    """The entries, each mirrored by its file in ``directory``.

    A class because the invariant (the file is written before the memory changes) must hold
    while two threads change the state. ``directory`` is ``None`` only when the SDK could not
    name the data directory; then the plugin has no captures and nothing is ever added.
    """

    def __init__(self, directory: Path | None, entries: Iterable[Entry] = ()) -> None:
        self._directory = directory
        self._entries = {entry.id: entry for entry in entries}
        self._lock = threading.Lock()
        self._woken = threading.Condition(self._lock)
        self._wake = False

    @classmethod
    def load(cls, directory: Path) -> tuple[Outbox, tuple[str, ...]]:
        """The outbox in ``directory``, made if missing, and the files it could not read.

        An entry left ``writing`` by a plugin that stopped mid-call becomes ``unknown``, on
        disk too, so its line is checked for before it is written again. A file that is not
        an entry is left where it is and named in the problems.

        An ``OSError`` from making or listing the directory passes through.
        """
        directory.mkdir(parents=True, exist_ok=True)
        entries: list[Entry] = []
        problems: list[str] = []
        for path in sorted(directory.glob("*.json")):
            try:
                found = from_json(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as error:  # EntryError is a ValueError
                problems.append(f"outbox: {path.name} is not an entry, and is left alone: {error}")
                continue
            started = on_start(found)
            if started != found:
                _save(directory, started)
            entries.append(started)
        return cls(directory, entries), tuple(problems)

    def entries(self) -> tuple[Entry, ...]:
        """Every entry, as it stands."""
        with self._lock:
            return tuple(self._entries.values())

    def get(self, entry_id: str) -> Entry | None:
        """One entry, or ``None`` when it is gone."""
        with self._lock:
            return self._entries.get(entry_id)

    def add(self, entry: Entry) -> None:
        """Keep a new entry, on disk first, and wake the thread.

        An ``OSError`` from writing the file passes through, and the entry is not kept.
        """
        with self._lock:
            self._write(entry)
            self._entries[entry.id] = entry
            self._wake = True
            self._woken.notify_all()

    def update(self, entry: Entry, *, unless_writing: bool = False) -> bool:
        """Replace an entry, on disk first. ``False`` when it is gone (discarded meanwhile).

        An ``OSError`` from writing the file passes through, and the entry is unchanged.

        Raises:
            BusyError: ``unless_writing`` is set and the entry is being written.
        """
        with self._lock:
            current = self._entries.get(entry.id)
            if current is None:
                return False
            if unless_writing and current.state is State.WRITING:
                raise BusyError(entry.id)
            self._write(entry)
            self._entries[entry.id] = entry
            self._wake = True
            self._woken.notify_all()
            return True

    def remove(self, entry_id: str, *, unless_writing: bool = False) -> None:
        """Forget an entry and delete its file.

        An ``OSError`` from deleting the file passes through, and the entry is kept.

        Raises:
            BusyError: ``unless_writing`` is set and the entry is being written.
        """
        with self._lock:
            current = self._entries.get(entry_id)
            if current is None:
                return
            if unless_writing and current.state is State.WRITING:
                raise BusyError(entry_id)
            if self._directory is not None:
                (self._directory / f"{entry_id}.json").unlink(missing_ok=True)
            del self._entries[entry_id]

    def wake(self) -> None:
        """Wake the thread now."""
        with self._lock:
            self._wake = True
            self._woken.notify_all()

    def sleep(self, seconds: float | None) -> None:
        """Wait until woken, or ``seconds`` pass; ``None`` waits until woken."""
        with self._lock:
            if not self._wake:
                self._woken.wait(seconds)
            self._wake = False

    def _write(self, entry: Entry) -> None:
        if self._directory is not None:
            _save(self._directory, entry)


def _save(directory: Path, entry: Entry) -> None:
    """Write one entry's file whole: a temporary name, fsync, rename.

    An ``OSError`` from the file system passes through.
    """
    final = directory / f"{entry.id}.json"
    temporary = directory / f".{entry.id}.json.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(to_json(entry), handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(final)
    # The rename lasts once the directory is on disk too; a system that cannot say so still
    # has the file, so this is a best effort.
    with contextlib.suppress(OSError):
        handle_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(handle_fd)
        finally:
            os.close(handle_fd)
