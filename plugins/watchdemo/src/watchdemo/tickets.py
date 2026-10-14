"""Tickets: what the JSON file holds, how it is checked, and how typed text matches it.

Pure: takes data and returns data. Reading the file is ``poller``'s and ``plugin``'s job.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Ticket:
    """One ticket. ``url`` is where Open goes; a ticket without one is copied instead."""

    id: str
    title: str
    status: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Match:
    """A ticket the typed text matched, and how well (``0.1..=1.0``)."""

    ticket: Ticket
    score: float


class TicketsError(ValueError):
    """The file's content is not a list of tickets. The message says which entry and why."""


def parse_tickets(raw: object) -> tuple[Ticket, ...]:
    """The tickets in decoded JSON, checked.

    Raises:
        TicketsError: ``raw`` is not a list of objects, an entry lacks a text ``id``,
            ``title`` or ``status`` (or has an empty one), ``url`` is given and is not
            non-empty text, or two entries have the same ``id``.
    """
    if not isinstance(raw, list):
        raise TicketsError(f"expected a list of tickets, found {_kind(raw)}")
    tickets: list[Ticket] = []
    seen: set[str] = set()
    for position, entry in enumerate(raw, start=1):
        ticket = _ticket(entry, position)
        if ticket.id in seen:
            raise TicketsError(f"ticket {position}: the id {ticket.id!r} appears twice")
        seen.add(ticket.id)
        tickets.append(ticket)
    return tuple(tickets)


def _kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "an object"
    if isinstance(value, str):
        return "text"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int | float):
        return "a number"
    return type(value).__name__


def _ticket(entry: object, position: int) -> Ticket:
    if not isinstance(entry, dict):
        raise TicketsError(f"ticket {position}: expected an object, found {_kind(entry)}")
    fields: dict[str, str] = {}
    for name in ("id", "title", "status"):
        value = entry.get(name)
        if not isinstance(value, str) or not value.strip():
            raise TicketsError(f"ticket {position}: {name!r} must be non-empty text")
        fields[name] = value.strip()
    url = entry.get("url")
    if url is not None and (not isinstance(url, str) or not url.strip()):
        raise TicketsError(f"ticket {position}: 'url' must be non-empty text when given")
    return Ticket(fields["id"], fields["title"], fields["status"], url.strip() if url else None)


_ID_THEN_SPACE = re.compile(r"(\S+)\s+")


def narrowed_id(text: str) -> str | None:
    """The id the text names, when it is one word followed by a space (``PROJ-1 ``).

    That is what Tab leaves in the input after completing a ticket, so it asks for that
    ticket alone. Text without the trailing space is a search.
    """
    found = _ID_THEN_SPACE.fullmatch(text.lstrip())
    return found.group(1) if found else None


def score(ticket: Ticket, text: str) -> float | None:
    """How well ``text`` matches the ticket, in ``0.5..=1.0``, or ``None`` for no match.

    The id counts for more than the title, and the start of either for more than the
    middle; case does not matter. Blank text matches everything, as 0.5.
    """
    needle = text.strip().casefold()
    if not needle:
        return 0.5
    id_, title = ticket.id.casefold(), ticket.title.casefold()
    tiers = (
        (id_ == needle, 1.0),
        (id_.startswith(needle), 0.9),
        (needle in id_, 0.8),
        (title.startswith(needle), 0.7),
        (re.search(rf"\b{re.escape(needle)}", title) is not None, 0.6),
        (needle in title, 0.5),
    )
    return next((points for hit, points in tiers if hit), None)


def find(tickets: Sequence[Ticket], text: str) -> tuple[Match, ...]:
    """The tickets for the typed text, best first and by id among equals.

    One word and a space names a ticket exactly; when no ticket has that id the text is
    searched like any other.
    """
    word = narrowed_id(text)
    if word is not None:
        exact = tuple(
            Match(ticket, 1.0) for ticket in tickets if ticket.id.casefold() == word.casefold()
        )
        if exact:
            return exact
    matches = [
        Match(ticket, points) for ticket in tickets if (points := score(ticket, text)) is not None
    ]
    return tuple(sorted(matches, key=lambda match: (-match.score, match.ticket.id)))
