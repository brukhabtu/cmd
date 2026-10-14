"""The sample tickets the demo works from when no tickets file is configured. Pure.

With no ``tickets`` setting the plugin keeps a file of its own in its data directory and
seeds it with these, so the demo works out of the box: watch a ticket, move it on, and be
told. Moving a ticket on is what stands in for a tracker changing under you.
"""

import json
from collections.abc import Sequence

from watchdemo.tickets import Ticket

SAMPLE_FILE = "tickets.json"
"""The sample file's name in the plugin's data directory."""

STATUSES = ("Open", "In Review", "Done")
"""The order the demo moves a ticket through, and back round."""

SAMPLE_TICKETS: tuple[Ticket, ...] = (
    Ticket(id="DEMO-1", title="Fix the login page", status="Open", url=None),
    Ticket(id="DEMO-2", title="Login emails bounce", status="In Review", url=None),
    Ticket(id="DEMO-3", title="Rotate the signing keys", status="Done", url=None),
)


def next_status(status: str) -> str:
    """The status after ``status``; one the demo does not know goes to the first."""
    if status not in STATUSES:
        return STATUSES[0]
    return STATUSES[(STATUSES.index(status) + 1) % len(STATUSES)]


def tickets_text(tickets: Sequence[Ticket]) -> str:
    """The tickets as the JSON file holds them."""
    entries = [
        {"id": t.id, "title": t.title, "status": t.status, **({"url": t.url} if t.url else {})}
        for t in tickets
    ]
    return json.dumps(entries, indent=2) + "\n"


def moved_on(tickets: Sequence[Ticket], ticket_id: str) -> tuple[Ticket, ...] | None:
    """The tickets with ``ticket_id`` moved to its next status, or ``None`` if it is not there."""
    if all(ticket.id != ticket_id for ticket in tickets):
        return None
    return tuple(
        Ticket(t.id, t.title, next_status(t.status), t.url) if t.id == ticket_id else t
        for t in tickets
    )
