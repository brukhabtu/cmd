"""What the plugin remembers: the watched ids, the status last seen of each, and recent moves.

Pure: a ``State`` is data, every change returns a new one, and the JSON form is checked on
the way in. Keeping it on disk is ``keeper``'s job.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

VERSION = 1
"""The version written into the file, so a later shape can tell an older one."""

RECENT_LIMIT = 50
"""The most changes kept."""


@dataclass(frozen=True, slots=True)
class Change:
    """A watched ticket whose status moved, noticed at ``at`` (local time, to the second)."""

    id: str
    title: str
    old: str
    new: str
    at: str


@dataclass(frozen=True, slots=True)
class State:
    """What is remembered.

    ``seen`` holds the status last seen of a watched ticket (absent until first seen);
    ``recent`` holds the changes noticed, newest first, at most ``RECENT_LIMIT``.
    """

    watched: frozenset[str] = frozenset()
    seen: Mapping[str, str] = field(default_factory=dict)
    recent: tuple[Change, ...] = ()


class StateError(ValueError):
    """The stored JSON is not a state this plugin wrote."""


def watch(state: State, ticket_id: str, status: str | None) -> State:
    """Start watching a ticket. ``status`` is what it is now, when known.

    Recording it here means a move between the click and the next poll is noticed rather
    than taken for the first sight. Watching what is already watched changes nothing.
    """
    if ticket_id in state.watched:
        return state
    seen = dict(state.seen)
    if status is not None:
        seen[ticket_id] = status
    return replace(state, watched=state.watched | {ticket_id}, seen=seen)


def unwatch(state: State, ticket_id: str) -> State:
    """Stop watching a ticket and forget its status. The changes already noticed stay."""
    if ticket_id not in state.watched:
        return state
    seen = {key: value for key, value in state.seen.items() if key != ticket_id}
    return replace(state, watched=state.watched - {ticket_id}, seen=seen)


def state_to_json(state: State) -> dict[str, Any]:
    """The state as a JSON-able dict, in a stable order."""
    return {
        "version": VERSION,
        "watched": sorted(state.watched),
        "seen": dict(sorted(state.seen.items())),
        "recent": [
            {"id": c.id, "title": c.title, "old": c.old, "new": c.new, "at": c.at}
            for c in state.recent
        ],
    }


def state_from_json(raw: object) -> State:
    """The state a ``state_to_json`` made.

    Raises:
        StateError: ``raw`` is not that shape: another version, a field missing or of the
            wrong kind, or a status kept for a ticket that is not watched.
    """
    if not isinstance(raw, dict) or raw.get("version") != VERSION:
        raise StateError(f"not a version {VERSION} state")
    watched = raw.get("watched")
    seen = raw.get("seen")
    recent = raw.get("recent")
    if not isinstance(watched, list) or not all(isinstance(item, str) for item in watched):
        raise StateError("`watched` is not a list of ids")
    if not isinstance(seen, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in seen.items()
    ):
        raise StateError("`seen` is not a map of id to status")
    if not set(seen) <= set(watched):
        raise StateError("`seen` holds a ticket that is not watched")
    if not isinstance(recent, list):
        raise StateError("`recent` is not a list")
    changes = tuple(_change(entry) for entry in recent[:RECENT_LIMIT])
    return State(frozenset(watched), dict(seen), changes)


def _change(entry: object) -> Change:
    names = ("id", "title", "old", "new", "at")
    if not isinstance(entry, dict) or not all(isinstance(entry.get(name), str) for name in names):
        raise StateError("`recent` holds an entry that is not a change")
    return Change(*(entry[name] for name in names))
