"""The shell of the watchdemo plugin: start, ``query``, ``home``, ``run`` and ``main``.

Decision 13. ``start`` reads the config and the saved state once and never raises; ``query``
and ``home`` read the tickets file afresh (it is small and local) and answer with rows, and
a file that cannot be used becomes a row; ``run`` performs Open, Copy, Watch and Unwatch.
``main`` starts the polling thread, then serves.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from cmd_sdk import (
    ConfigError,
    Copy,
    Description,
    Effect,
    Item,
    MissingVariableError,
    Open,
    Plugin,
    Show,
    config,
    data_dir,
    serve,
)

from watchdemo.keeper import Store
from watchdemo.options import Settings, parse_options
from watchdemo.poller import Poller, SourceError, read_tickets
from watchdemo.rows import KEYWORD, home_rows, query_rows
from watchdemo.state import unwatch, watch
from watchdemo.tickets import Ticket

DESCRIPTION = Description(name="watchdemo", version="0.1.0", keyword=KEYWORD, home=True)


@dataclass(frozen=True, slots=True)
class Demo:
    """Everything ``query``, ``home`` and ``run`` work from, made once by ``start``."""

    settings: Settings
    store: Store


def start() -> Demo:
    """Read the config and the saved state. Never raises: what went wrong becomes rows."""
    try:
        directory: Path | None = data_dir()
    except MissingVariableError as error:
        sys.stderr.write(f"watchdemo: {error}; nothing watched is kept\n")
        directory = None
    store = Store.load(directory)
    try:
        settings = parse_options(config())
    except (ConfigError, MissingVariableError) as error:
        settings = Settings(notes=(str(error),))
    return Demo(settings, store)


def _tickets(demo: Demo) -> tuple[tuple[Ticket, ...] | None, tuple[str, ...], tuple[str, ...]]:
    """The tickets now, or ``None``; the problems that explain ``None``; the notes otherwise."""
    notes = (*demo.settings.notes, *([demo.store.recovered] if demo.store.recovered else []))
    if demo.settings.tickets is None:
        return None, notes, ()
    try:
        return read_tickets(Path(demo.settings.tickets)), (), notes
    except SourceError as error:
        return None, (str(error), *notes), ()


def query(demo: Demo, text: str) -> tuple[Item, ...]:
    """The rows for the text after ``watch``."""
    tickets, problems, notes = _tickets(demo)
    return query_rows(text, tickets, demo.store.state, problems, notes)


def home(demo: Demo) -> tuple[Item, ...]:
    """The rows for the blank input: what moved, and what is watched."""
    tickets, problems, notes = _tickets(demo)
    return home_rows(tickets, demo.store.state, problems, notes)


def run(demo: Demo, item: str, action: str) -> Effect:
    """Perform an action on a ticket. A row with no ticket (``item`` is empty) only explains."""
    if not item:
        return Show(
            text="Set `tickets` in config.toml to a JSON file of tickets, then type "
            f"{KEYWORD} and part of a title"
        )
    if action == "copy":
        return Copy(text=item)
    if action == "unwatch":
        demo.store.transact(lambda state: (unwatch(state, item), None))
        return Show(text=f"Stopped watching {item}")
    if action in {"open", "watch"}:
        return _with_ticket(demo, item, action)
    return Show(text=f"watchdemo has no action {action!r}")


def _with_ticket(demo: Demo, item: str, action: str) -> Effect:
    """Open and Watch need the ticket as the file has it now."""
    tickets, problems, _ = _tickets(demo)
    if tickets is None:
        return Show(text=problems[0])
    ticket = next((found for found in tickets if found.id == item), None)
    if ticket is None:
        return Show(text=f"{item} is not in the tickets file")
    if action == "open":
        return Open(target=ticket.url) if ticket.url else Copy(text=item)
    demo.store.transact(lambda state: (watch(state, item, ticket.status), None))
    return Show(text=f"Watching {item}")


def plugin(demo: Demo) -> Plugin:
    """The plugin for this demo."""
    return Plugin(
        DESCRIPTION,
        lambda text: query(demo, text),
        lambda item, action: run(demo, item, action),
        home=lambda: home(demo),
    )


def main() -> None:
    """Start the polling thread when there is a file to poll, then serve."""
    demo = start()
    if demo.settings.tickets is not None:
        Poller(Path(demo.settings.tickets), demo.settings.interval, demo.store).start()
    serve(plugin(demo))
