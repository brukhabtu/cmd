"""The rows the plugin shows, built from tickets and state. Pure.

A ticket row carries ``complete`` (Tab narrows to it) and its actions; a suggestion has
``complete`` and none, so the host completes it on Enter (decision 13). Rows that explain
(a problem, nothing to show) have neither: Enter on one only shows a line.
"""

from collections.abc import Sequence

from cmd_sdk import Action, Item, SymbolIcon

from watchdemo.state import Change, State
from watchdemo.tickets import Ticket, find, narrowed_id

KEYWORD = "watch"
WATCHING = "watching"
"""The word after the keyword that lists what is watched."""

HOME_CHANGES = 8
"""How many recent changes the home list shows."""

_WATCHED_ICON = SymbolIcon("eye")
_TICKET_ICON = SymbolIcon("ticket")


def complete_text(ticket_id: str) -> str:
    """What Tab puts in the input for a ticket: the keyword, the id and a space."""
    return f"{KEYWORD} {ticket_id} "


def actions_for(
    *, url: str | None, watched: bool, toggle_first: bool = False
) -> tuple[Action, ...]:
    """Open (or copy the id, for a ticket with no address), then Watch or Unwatch, then Copy.

    With ``toggle_first`` the Watch or Unwatch comes first, so Enter does it: the window
    runs only a row's first action until the actions menu exists (DRAFT-6), and a ticket
    narrowed to by Tab is where the person has chosen the noun and wants the verb.
    """
    toggle = Action("unwatch", "Unwatch") if watched else Action("watch", "Watch")
    others = (
        (Action("open", "Open"), Action("copy", "Copy id")) if url else (Action("copy", "Copy id"),)
    )
    return (toggle, *others) if toggle_first else (others[0], toggle, *others[1:])


def ticket_item(
    ticket: Ticket, *, watched: bool, score: float | None = None, toggle_first: bool = False
) -> Item:
    """The row for a ticket."""
    return Item(
        id=ticket.id,
        title=f"{ticket.id}  {ticket.title}",
        subtitle=f"{ticket.status} · watching" if watched else ticket.status,
        score=score,
        actions=actions_for(url=ticket.url, watched=watched, toggle_first=toggle_first),
        icon=_WATCHED_ICON if watched else _TICKET_ICON,
        complete=complete_text(ticket.id),
    )


def missing_item(ticket_id: str) -> Item:
    """The row for a watched ticket the file no longer holds: it can only be dropped."""
    return Item(
        id=ticket_id,
        title=f"{ticket_id}  (not in the tickets file)",
        subtitle="watching",
        actions=(Action("unwatch", "Unwatch"),),
        icon=_WATCHED_ICON,
    )


def change_item(change: Change, ticket: Ticket | None, *, watched: bool) -> Item:
    """The row for a recorded change. ``ticket`` is the ticket as it is now, if it still is."""
    when = change.at.replace("T", " ")
    return Item(
        id=change.id,
        title=f"{change.id}: {change.old} -> {change.new}",
        subtitle=f"{change.title} · {when}",
        actions=actions_for(url=ticket.url if ticket else None, watched=watched),
        icon=_WATCHED_ICON if watched else _TICKET_ICON,
        complete=complete_text(change.id),
    )


def suggestion_item(count: int) -> Item:
    """``Watching (N)``: a suggestion that completes to the list of what is watched."""
    return Item(
        id="",
        title=f"Watching ({count})",
        subtitle="The tickets you watch, and where each stands",
        icon=_WATCHED_ICON,
        complete=f"{KEYWORD} {WATCHING}",
    )


def note_item(title: str, subtitle: str | None = None, *, complete: str | None = None) -> Item:
    """A row that says something and does nothing."""
    return Item(id="", title=title, subtitle=subtitle, complete=complete)


def problem_items(problems: Sequence[str]) -> tuple[Item, ...]:
    """One row per problem; the first is the one to fix."""
    return tuple(note_item(problem) for problem in problems)


def watched_items(tickets: Sequence[Ticket], state: State) -> tuple[Item, ...]:
    """The watched tickets as the file has them, in file order; then those it no longer holds."""
    present = {ticket.id for ticket in tickets}
    rows = [ticket_item(ticket, watched=True) for ticket in tickets if ticket.id in state.watched]
    rows += [missing_item(ticket_id) for ticket_id in sorted(state.watched - present)]
    return tuple(rows)


def query_rows(
    text: str,
    tickets: Sequence[Ticket] | None,
    state: State,
    problems: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> tuple[Item, ...]:
    """The rows for the text after the keyword.

    ``tickets`` is ``None`` when the file cannot be used and ``problems`` say why; then the
    problems are the whole answer. ``notes`` (a setting that was corrected, a state file
    that was rebuilt) are shown after the rest of a blank query.
    """
    if tickets is None:
        return problem_items(problems or ("The tickets file cannot be used",))
    word = text.strip().casefold()
    if word == WATCHING:
        return watched_items(tickets, state) or (
            note_item("Nothing is watched yet", f"Type {KEYWORD} and a ticket, then choose Watch"),
        )
    matches = find(tickets, text)
    named = narrowed_id(text)
    narrowed = (
        named is not None
        and len(matches) == 1
        and matches[0].ticket.id.casefold() == named.casefold()
    )
    rows = [
        ticket_item(
            match.ticket,
            watched=match.ticket.id in state.watched,
            score=match.score,
            toggle_first=narrowed,
        )
        for match in matches
    ]
    if not word or WATCHING.startswith(word):
        rows.append(suggestion_item(len(state.watched)))
    if not rows:
        rows.append(note_item(f"No ticket matches {text.strip()!r}"))
    if not word:
        rows += [note_item(note) for note in notes]
    return tuple(rows)


def home_rows(
    tickets: Sequence[Ticket] | None,
    state: State,
    problems: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> tuple[Item, ...]:
    """The blank input: what moved, newest first, then what is watched and where it stands."""
    by_id = {ticket.id: ticket for ticket in tickets or ()}
    rows: list[Item] = []
    if tickets is None:
        rows += problem_items(problems or ("The tickets file cannot be used",))
    rows += [
        change_item(change, by_id.get(change.id), watched=change.id in state.watched)
        for change in state.recent[:HOME_CHANGES]
    ]
    if tickets is not None:
        rows += watched_items(tickets, state)
    if not rows:
        rows.append(
            note_item(
                "Nothing watched yet",
                f"Type {KEYWORD} and a ticket, then choose Watch",
                complete=f"{KEYWORD} ",
            )
        )
    rows += [note_item(note) for note in notes]
    return tuple(rows)
