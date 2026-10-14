"""The shell of the watchdemo plugin: start, ``query``, ``home``, ``run`` and ``main``.

Decision 13. ``start`` reads the config and the saved state once and never raises; ``query``
and ``home`` read the tickets file afresh (it is small and local) and answer with rows, and
a file that cannot be used becomes a row; ``run`` performs Open, Copy, Watch and Unwatch.
``main`` starts the polling thread, then serves.
"""

import os
import sys
import tempfile
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from cmd_sdk import (
    Action,
    Agreement,
    ConfigError,
    Copy,
    Description,
    Effect,
    Item,
    MissingVariableError,
    Open,
    Plugin,
    Show,
    SymbolIcon,
    config,
    data_dir,
    serve,
)

from watchdemo.keeper import Store
from watchdemo.options import UNSET, Settings, parse_options
from watchdemo.poller import Poller, SourceError, read_tickets
from watchdemo.rows import KEYWORD, home_rows, query_rows
from watchdemo.sample import SAMPLE_FILE, SAMPLE_TICKETS, moved_on, tickets_text
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
    if directory is not None and settings.tickets is None and settings.notes[:1] == (UNSET,):
        settings = _sample_settings(settings, directory)
    return Demo(settings, store)


def _sample_settings(settings: Settings, directory: Path) -> Settings:
    """With no tickets file configured, work from a sample file in the data directory.

    It is made the first time and never overwritten, so the person can edit it. If it cannot
    be made the settings stay as they were, and the rows say what to configure.
    """
    path = directory / SAMPLE_FILE
    if not path.exists():
        try:
            _write_atomically(path, tickets_text(SAMPLE_TICKETS))
        except OSError as error:
            sys.stderr.write(f"watchdemo: could not make the sample tickets: {error}\n")
            return settings
    return replace(settings, tickets=str(path), notes=settings.notes[1:], sample=True)


def _write_atomically(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` so a reader sees the old file or the new, never half."""
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}.", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
    Path(handle.name).replace(path)


def _tickets(demo: Demo) -> tuple[tuple[Ticket, ...] | None, tuple[str, ...], tuple[str, ...]]:
    """The tickets now, or ``None``; the problems that explain ``None``; the notes otherwise."""
    notes = (*demo.settings.notes, *([demo.store.recovered] if demo.store.recovered else []))
    if demo.settings.tickets is None:
        return None, notes, ()
    try:
        return read_tickets(Path(demo.settings.tickets)), (), notes
    except SourceError as error:
        return None, (str(error), *notes), ()


MOVE_ID = "sample:move"
EDIT_ID = "sample:edit"
"""The ids of the two rows the sample mode adds; no ticket has these (a ticket id has no colon)."""


def _sample_rows(demo: Demo) -> tuple[Item, ...]:
    """In sample mode, the way to make something move: no tracker is changing under you."""
    if not demo.settings.sample or demo.settings.tickets is None:
        return ()
    return (
        Item(
            id=MOVE_ID,
            title="Move a watched ticket on (demo)",
            subtitle="Changes its status in the sample file; you are told within a few seconds",
            score=0.05,
            actions=(Action("move", "Move it on"),),
            icon=SymbolIcon("forward"),
        ),
        Item(
            id=EDIT_ID,
            title="Edit the sample tickets",
            subtitle=demo.settings.tickets,
            score=0.04,
            actions=(Action("open", "Open the file"),),
            icon=SymbolIcon("doc.text"),
        ),
    )


def query(demo: Demo, text: str) -> tuple[Item, ...]:
    """The rows for the text after ``watch``."""
    tickets, problems, notes = _tickets(demo)
    rows = query_rows(text, tickets, demo.store.state, problems, notes)
    if text.strip().casefold() in {"", "demo", "move", "edit"}:
        rows = (*rows, *_sample_rows(demo))
    return rows


def home(demo: Demo) -> tuple[Item, ...]:
    """The rows for the blank input: what moved, and what is watched.

    A plugin whose config does not name a tickets file has nothing to show, and says so
    only when asked (``watch``): it does not take the top of the list every time the window
    opens. A config that is wrong, or a file that is set but cannot be read, is a failure
    and is shown.
    """
    if demo.settings.tickets is None and demo.settings.notes[:1] == (UNSET,):
        return ()
    tickets, problems, notes = _tickets(demo)
    return (*home_rows(tickets, demo.store.state, problems, notes), *_sample_rows(demo))


def run(demo: Demo, item: str, action: str) -> Effect:
    """Perform an action on a ticket. A row with no ticket (``item`` is empty) only explains."""
    if not item:
        where = os.environ.get("CMD_PLUGIN_CONFIG")
        target = f"{where}/config.toml" if where else "this plugin's config.toml"
        return Show(
            text=f'Put tickets = "/path/to/tickets.json" in {target}, then type '
            f"{KEYWORD} and part of a title"
        )
    sample = _sample_action(demo, item)
    if sample is not None:
        return sample
    if action == "copy":
        return Copy(text=item)
    if action == "unwatch":
        demo.store.transact(lambda state: (unwatch(state, item), None))
        return Show(text=f"Stopped watching {item}")
    if action in {"open", "watch"}:
        return _with_ticket(demo, item, action)
    return Show(text=f"watchdemo has no action {action!r}")


def _sample_action(demo: Demo, item: str) -> Effect | None:
    """What Enter does on one of the sample mode's two rows; ``None`` for any other row."""
    if item == MOVE_ID:
        return _move_on(demo)
    if item == EDIT_ID:
        return Open(target=Path(demo.settings.tickets or "").as_uri())
    return None


def _move_on(demo: Demo) -> Effect:
    """Move the first watched ticket (in file order) to its next status in the sample file."""
    tickets, problems, _ = _tickets(demo)
    if tickets is None or demo.settings.tickets is None:
        return Show(text=problems[0] if problems else "There is no tickets file to change")
    chosen = next((t for t in tickets if t.id in demo.store.state.watched), None)
    if chosen is None:
        return Show(text="Watch a ticket first: type watch, pick one, press Tab, then Enter")
    moved = moved_on(tickets, chosen.id)
    if moved is None:
        return Show(text=f"{chosen.id} is not in the tickets file")
    try:
        _write_atomically(Path(demo.settings.tickets), tickets_text(moved))
    except OSError as error:
        return Show(text=f"Could not change the sample file: {error}")
    now = next(t.status for t in moved if t.id == chosen.id)
    return Show(
        text=f"Moved {chosen.id} to {now}; you will be told within {demo.settings.interval:g} s"
    )


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


def plugin(demo: Demo, poller: Poller | None = None) -> Plugin:
    """The plugin for this demo.

    With a ``poller`` it is started when the host's ``describe`` arrives, after the SDK has
    agreed the capabilities: a change found by an earlier poll would be reported to nobody.
    """
    started = threading.Event()

    def described(_agreement: Agreement) -> Description:
        if poller is not None and not started.is_set():
            started.set()
            poller.start()
        return DESCRIPTION

    return Plugin(
        DESCRIPTION,
        lambda text: query(demo, text),
        lambda item, action: run(demo, item, action),
        home=lambda: home(demo),
        describe=described,
    )


def main() -> None:
    """Serve, polling the tickets file once the host's describe has been answered."""
    demo = start()
    poller = (
        Poller(Path(demo.settings.tickets), demo.settings.interval, demo.store)
        if demo.settings.tickets is not None
        else None
    )
    serve(plugin(demo, poller))
