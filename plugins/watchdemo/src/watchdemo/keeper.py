"""The state on disk: read tolerantly, written atomically, changed under one lock.

The shell around ``state``. The plugin's query and run (the serve thread) and the polling
thread both change the state, so every change goes through ``Store.transact``.
"""

import contextlib
import json
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from watchdemo.state import State, StateError, state_from_json, state_to_json

STATE_FILE = "state.json"
CORRUPT_SUFFIX = ".corrupt"


class Store:
    """The current ``State`` and the file that keeps it.

    With no ``directory`` the state lives in memory only, which is what the plugin has when
    the host gave it no data directory. A write that fails is logged and the state goes on
    in memory: the next change tries again.
    """

    def __init__(self, directory: Path | None, state: State, recovered: str | None = None) -> None:
        self._path = None if directory is None else directory / STATE_FILE
        self._state = state
        self._lock = threading.Lock()
        self.recovered = recovered
        """Why the file was not used, when it was corrupt and the state started empty."""

    @classmethod
    def load(cls, directory: Path | None) -> Store:
        """Read the file in ``directory``. Never raises.

        A missing one is an empty state; an unreadable or corrupt one is set aside as
        ``state.json.corrupt``, noted once on stderr, and the state starts empty.
        """
        if directory is None:
            return cls(None, State())
        path = directory / STATE_FILE
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls(directory, State())
        except OSError as error:
            return cls(directory, State(), _recovered(path, f"cannot be read: {error.strerror}"))
        try:
            return cls(directory, state_from_json(json.loads(text)))
        except (ValueError, StateError) as error:
            aside = path.with_name(path.name + CORRUPT_SUFFIX)
            with contextlib.suppress(OSError):  # it stays and the next write replaces it
                path.replace(aside)
            return cls(directory, State(), _recovered(path, f"is not a saved state: {error}"))

    @property
    def state(self) -> State:
        """The current state."""
        with self._lock:
            return self._state

    def transact[T](self, change: Callable[[State], tuple[State, T]]) -> T:
        """Apply ``change`` to the state, keep the result, and return what it returned.

        ``change`` runs under the lock, so it must not touch the store or block.
        """
        with self._lock:
            state, result = change(self._state)
            if state is not self._state:
                self._state = state
                self._write(state)
            return result

    def _write(self, state: State) -> None:
        if self._path is None:
            return
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(state_to_json(state), indent=1), encoding="utf-8")
            temporary.replace(self._path)
        except OSError as error:
            sys.stderr.write(f"watchdemo: cannot keep {self._path}: {error}\n")


def _recovered(path: Path, why: str) -> str:
    message = f"{path} {why}; started with nothing watched"
    sys.stderr.write(f"watchdemo: {message}\n")
    return message
