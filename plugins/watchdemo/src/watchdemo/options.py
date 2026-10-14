"""The plugin's settings, from the decoded ``config.toml``. Pure.

A bad setting is a note for the person, never a crash: without ``tickets`` the plugin
shows rows that say what to write, and a bad ``interval`` falls back with a note.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_INTERVAL = 5.0
"""Seconds between two reads of the tickets file."""

MIN_INTERVAL = 0.5
"""The least the interval can be: a smaller one is raised to it."""


@dataclass(frozen=True, slots=True)
class Settings:
    """What the config says. ``tickets`` is ``None`` when it is unusable, and ``notes`` say why."""

    tickets: str | None = None
    interval: float = DEFAULT_INTERVAL
    notes: tuple[str, ...] = ()
    sample: bool = False
    """True when ``tickets`` is the plugin's own sample file, because none was configured."""


UNSET = "config.toml: set `tickets` to the path of the tickets JSON file"
"""The note for a config that does not name a tickets file: not a fault, only not set up."""


def parse_options(raw: Mapping[str, Any]) -> Settings:
    """The settings in a decoded config. Never raises."""
    notes: list[str] = []
    tickets = raw.get("tickets")
    if tickets is None:
        notes.append(UNSET)
    elif not isinstance(tickets, str) or not tickets.strip():
        notes.append("config.toml: `tickets` must be the path of a file, as text")
        tickets = None
    interval = DEFAULT_INTERVAL
    if "interval" in raw:
        given = raw["interval"]
        if (
            isinstance(given, bool)
            or not isinstance(given, int | float)
            or not math.isfinite(given)
        ):
            notes.append(f"config.toml: `interval` must be a number of seconds; using {interval:g}")
        elif given < MIN_INTERVAL:
            interval = MIN_INTERVAL
            notes.append(
                f"config.toml: `interval` is at least {MIN_INTERVAL:g}; using {interval:g}"
            )
        else:
            interval = float(given)
    return Settings(tickets.strip() if isinstance(tickets, str) else None, interval, tuple(notes))
