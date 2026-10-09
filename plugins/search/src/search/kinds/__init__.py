"""The provider kinds, and the interface each one is (decision 11).

A kind is a module with the names ``Kind`` lists. ``KINDS`` maps the config's ``kind`` to
it, so a new kind is one module and one line here. A kind is pure: it says what to run and
what the answer means, and the shell does the running.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from cmd_sdk import CallResult

from search.hits import Failed, Found, Hit, InvalidError, Outcome
from search.kinds import command, qmd

__all__ = ["KINDS", "Failed", "Found", "Hit", "InvalidError", "Kind", "Outcome"]


class Kind[S](Protocol):
    """What a kind module has. ``S`` is its own settings, which ``parse`` makes."""

    KEYS: frozenset[str]
    """The keys this kind adds to a ``[[provider]]`` table."""

    REFERENCE: str
    """The title of the action that copies ``Hit.reference`` ("Copy docid")."""

    def parse(self, table: Mapping[str, Any]) -> S:
        """Its own keys of a provider's table; raises ``InvalidError`` saying what is wrong."""
        ...

    def executable(self, settings: S) -> str:
        """The program, which the shell checks at start."""
        ...

    def arguments(self, settings: S, text: str, limit: int) -> tuple[str, ...]:
        """The arguments after the program, for this text and limit."""
        ...

    def read(self, settings: S, finished: CallResult, cwd: Path, limit: int) -> Outcome:
        """What the call's answer means, a timed-out call's included."""
        ...

    def scope(self, settings: S) -> str:
        """What the no-hits row names besides the provider (qmd's index), or ``""``."""
        ...


KINDS: Mapping[str, Kind[Any]] = {"qmd": qmd, "command": command}
"""Each kind by the name a config gives it."""
