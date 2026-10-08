"""The pure half of ``query`` and ``run``: which keyword was typed, the rows, what an id means.

The plugin declares no keyword (decision 10, until draft 5), so it sees nearly every
keystroke: ``route`` answers ``None`` for text whose first word is none of its keywords,
and the shell returns no rows at once. Everything the rows need comes in as data: the
settings, how the start went, the outbox as it stands, whether Obsidian is running and,
for a view, what the CLI answered.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import assert_never

from cmd_sdk import Action, Item, SymbolIcon

from vault.invocations import folder, note_name
from vault.outbox import MAX_TRIES, Entry, State, age, render
from vault.schema import (
    BUILT_CAPTURES,
    BUILT_VIEWS,
    DAILY,
    Capture,
    CaptureKind,
    Settings,
    View,
    fold,
)

OUTBOX_ROWS = 3
"""How many outbox rows a keyword's answer carries before "N more: type vault"."""

RETRY = "retry"
COPY = "copy"
DISCARD = "discard"

NOTHING_CAPTURED = "nothing is captured until this is fixed"

_CAPTURE_ICON = SymbolIcon("square.and.pencil")
_VIEW_ICON = SymbolIcon("magnifyingglass")
_OUTBOX_ICON = SymbolIcon("tray.full")
_PROBLEM_ICON = SymbolIcon("exclamationmark.triangle")
_STATUS_ICON = SymbolIcon("books.vertical")


@dataclass(frozen=True, slots=True)
class Startup:
    """How the plugin's start went, beyond what the settings say.

    ``config_directory`` is where ``config.toml`` belongs, when the SDK could say.
    ``no_config`` is a missing or empty file. ``unreadable`` is the SDK's message for a file
    that did not parse or could not be read; ``stale_keywords`` are the keywords of the last
    config that parsed, which then show it. ``problems`` are the start's own: a directory
    the SDK could not find, an outbox file that is not an entry.
    """

    settings: Settings
    config_directory: str | None = None
    no_config: bool = False
    unreadable: str | None = None
    stale_keywords: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


# --- which keyword ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Status:
    """The status keyword: Obsidian, the config's problems, the whole outbox."""


@dataclass(frozen=True, slots=True)
class ToCapture:
    """A capture keyword and the text after it."""

    capture: Capture
    text: str


@dataclass(frozen=True, slots=True)
class ToView:
    """A view keyword and the text after it."""

    view: View
    text: str


@dataclass(frozen=True, slots=True)
class Unbuilt:
    """A valid entry of a kind this slice does not build yet."""

    keyword: str
    kind: str


@dataclass(frozen=True, slots=True)
class Misconfigured:
    """A keyword whose entry the config got wrong, or every keyword of an unreadable config."""

    keyword: str
    messages: tuple[str, ...]


type Route = Status | ToCapture | ToView | Unbuilt | Misconfigured


def route(text: str, startup: Startup) -> Route | None:
    """Which of the plugin's keywords starts ``text``, ASCII case ignored; ``None`` if none."""
    parts = text.split(maxsplit=1)
    if not parts:
        return None
    word = fold(parts[0])
    rest = parts[1].strip() if len(parts) > 1 else ""
    if word == fold(startup.settings.status_keyword):
        return Status()
    return _entry_route(word, rest, startup.settings) or _problem_route(parts[0], startup)


def _entry_route(word: str, rest: str, settings: Settings) -> Route | None:
    for capture in settings.captures:
        if word == fold(capture.keyword):
            if capture.kind not in BUILT_CAPTURES:
                return Unbuilt(capture.keyword, f"capture of kind {capture.kind.value!r}")
            return ToCapture(capture, rest)
    for view in settings.views:
        if word == fold(view.keyword):
            if view.kind not in BUILT_VIEWS:
                return Unbuilt(view.keyword, f"view of kind {view.kind.value!r}")
            return ToView(view, rest)
    return None


def _problem_route(typed: str, startup: Startup) -> Route | None:
    word = fold(typed)
    messages = tuple(
        problem.message
        for problem in startup.settings.problems
        if problem.keyword is not None and fold(problem.keyword) == word
    )
    if messages:
        return Misconfigured(typed, messages)
    if startup.unreadable is not None and word in {fold(old) for old in startup.stale_keywords}:
        return Misconfigured(typed, (f"{startup.unreadable}; {NOTHING_CAPTURED}",))
    return None


# --- what an id means ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Queue:
    """Enter on a capture: queue it."""

    keyword: str
    text: str


@dataclass(frozen=True, slots=True)
class Say:
    """Enter on a row that only informs: keep the launcher open and say this."""

    text: str


@dataclass(frozen=True, slots=True)
class OnEntry:
    """An action on an outbox entry."""

    entry_id: str


@dataclass(frozen=True, slots=True)
class OpenNote:
    """Enter on a search result: open the note."""

    path: str


@dataclass(frozen=True, slots=True)
class OpenApp:
    """Enter on "Obsidian is not running": start it."""


@dataclass(frozen=True, slots=True)
class OpenConfig:
    """Enter on "No config": open the directory where it belongs."""


type Choice = Queue | Say | OnEntry | OpenNote | OpenApp | OpenConfig


def choice(item: str) -> Choice:  # ruff: ignore[too-many-return-statements] - one return per kind of id
    """What a row's id asks ``run`` to do. An id this plugin did not make says so."""
    kind, _, rest = item.partition(":")
    match kind:
        case "capture":
            keyword, _, text = rest.partition(" ")
            return Queue(keyword, text)
        case "say":
            return Say(rest)
        case "outbox":
            return OnEntry(rest)
        case "note":
            return OpenNote(rest)
        case "app":
            return OpenApp()
        case "config":
            return OpenConfig()
        case _:
            return Say(f"vault made no row {item!r}")


# --- the rows -----------------------------------------------------------------------------


def _say(title: str, subtitle: str | None = None, icon: SymbolIcon = _PROBLEM_ICON) -> Item:
    return Item(id=f"say:{title}", title=title, subtitle=subtitle, icon=icon)


def _app_row(*, running: bool) -> Item:
    if running:
        return _say("Obsidian is running", icon=_STATUS_ICON)
    return Item(
        id="app:",
        title="Obsidian is not running",
        subtitle="Enter opens Obsidian",
        icon=_STATUS_ICON,
    )


def where(target: str) -> str:
    """A target as a row names it."""
    return "today's daily note" if target == DAILY else target


def _describe(capture: Capture) -> str:
    under = f", under {capture.heading}" if capture.heading is not None else ""
    return f"{where(capture.target)}{under}"


def capture_rows(
    route: ToCapture, settings: Settings, now: datetime, *, running: bool
) -> tuple[Item, ...]:
    """The rows for a capture keyword: what Enter will write, and where.

    Built from the config alone: no CLI call, no file read. ``running`` only adds that a
    capture made now waits for Obsidian.
    """
    capture = route.capture
    if not route.text:
        return (
            Item(
                id=f"say:Type the text after {capture.keyword}",
                title=f"{capture.keyword} <text>",
                subtitle=f"Adds a line to {_describe(capture)}",
                icon=_CAPTURE_ICON,
            ),
        )
    line, target = render(capture, route.text, now, settings.date_format, settings.time_format)
    under = f", under {capture.heading}" if capture.heading is not None else ""
    subtitle = f"{capture.keyword}: {where(target)}{under}"
    if not running:
        subtitle += "; Obsidian is not running: kept until it opens"
    return (
        Item(
            id=f"capture:{capture.keyword} {route.text}",
            title=line,
            subtitle=subtitle,
            icon=_CAPTURE_ICON,
        ),
    )


@dataclass(frozen=True, slots=True)
class Hits:
    """The notes a search found."""

    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NotRunning:
    """Obsidian is not running, so the CLI was not called."""


@dataclass(frozen=True, slots=True)
class Unanswered:
    """The CLI was called and did not answer: ``message`` says how."""

    message: str


type Searched = Hits | NotRunning | Unanswered


def view_rows(route: ToView, searched: Searched | None) -> tuple[Item, ...]:
    """The rows for a search view. ``searched`` is ``None`` when there was nothing to search."""
    view = route.view
    if not route.text or searched is None:
        return (
            Item(
                id=f"say:Type text after {view.keyword} to search the vault",
                title="Search the vault",
                subtitle=f"Type text after {view.keyword}",
                icon=_VIEW_ICON,
            ),
        )
    match searched:
        case NotRunning():
            return (_app_row(running=False),)
        case Unanswered():
            return (_say(searched.message),)
        case Hits():
            if not searched.paths:
                return (_say(f"No notes match {route.text!r}", icon=_VIEW_ICON),)
            return tuple(
                Item(
                    id=f"note:{path}", title=note_name(path), subtitle=folder(path), icon=_VIEW_ICON
                )
                for path in searched.paths
            )
        case _ as unreachable:
            assert_never(unreachable)


def problem_rows(route: Unbuilt | Misconfigured) -> tuple[Item, ...]:
    """The rows for a keyword this plugin knows and cannot serve."""
    match route:
        case Unbuilt():
            return (
                _say(
                    f"{route.keyword}: a {route.kind} is not built yet",
                    "Nothing is captured or shown; the config entry is kept for when it is",
                ),
            )
        case Misconfigured():
            return tuple(_say(message) for message in route.messages)
        case _ as unreachable:
            assert_never(unreachable)


def everywhere_rows(settings: Settings) -> tuple[Item, ...]:
    """The problems that stop every write, shown on every keyword."""
    return tuple(_say(problem.message) for problem in settings.problems if problem.everywhere)


def status_rows(
    startup: Startup, entries: Sequence[Entry], time_format: str, *, running: bool
) -> tuple[Item, ...]:
    """The status keyword: Obsidian, every config problem, every outbox entry."""
    settings = startup.settings
    rows = [_app_row(running=running)]
    if startup.no_config and startup.config_directory is not None:
        rows.append(
            Item(
                id="config:",
                title=f"No config: create config.toml in {startup.config_directory}",
                subtitle="Enter opens the directory",
                icon=_PROBLEM_ICON,
            )
        )
    if startup.unreadable is not None:
        rows.append(_say(startup.unreadable, NOTHING_CAPTURED))
    rows += [_say(problem) for problem in startup.problems]
    rows += [_say(problem.message) for problem in settings.problems]
    rows += [
        problem_rows(Unbuilt(capture.keyword, f"capture of kind {capture.kind.value!r}"))[0]
        for capture in settings.captures
        if capture.kind not in BUILT_CAPTURES
    ]
    rows += [
        problem_rows(Unbuilt(view.keyword, f"view of kind {view.kind.value!r}"))[0]
        for view in settings.views
        if view.kind not in BUILT_VIEWS
    ]
    rows += [entry_row(entry, time_format, running=running) for entry in ordered(entries)]
    keywords = settings.keywords()[1:]
    if len(rows) == 1 and keywords:
        rows.append(
            _say(f"Keywords: {', '.join(keywords)}", "Nothing waits to be written", _STATUS_ICON)
        )
    return tuple(rows)


def outbox_rows(
    entries: Sequence[Entry], status_keyword: str, time_format: str, *, running: bool
) -> tuple[Item, ...]:
    """Up to ``OUTBOX_ROWS`` outbox rows for a keyword's answer, then how many more."""
    shown = ordered(entries)
    rows = [entry_row(entry, time_format, running=running) for entry in shown[:OUTBOX_ROWS]]
    if len(shown) > OUTBOX_ROWS:
        more = len(shown) - OUTBOX_ROWS
        rows.append(_say(f"{more} more: type {status_keyword}", icon=_OUTBOX_ICON))
    return tuple(rows)


_ORDER = {State.FAILED: 0, State.UNKNOWN: 1, State.WRITING: 2, State.PENDING: 3}


def ordered(entries: Sequence[Entry]) -> list[Entry]:
    """Entries that need the person first, then oldest first."""
    return sorted(entries, key=lambda entry: (_ORDER[entry.state], *age(entry)))


def entry_row(entry: Entry, time_format: str, *, running: bool) -> Item:
    """One outbox entry as decision 10's table shows it."""
    what = entry.target if entry.kind is CaptureKind.OPEN else entry.line
    copy = Action(COPY, "Copy")
    discard = Action(DISCARD, "Discard")
    match entry.state:
        case State.PENDING if entry.attempts:
            at = entry.next_try.strftime(time_format) if entry.next_try is not None else "once due"
            title = f"Waiting: {what}"
            subtitle = f"try {entry.attempts + 1} of {MAX_TRIES} at {at}: {entry.last_error}"
            actions: tuple[Action, ...] = (Action(RETRY, "Retry now"), copy, discard)
        case State.PENDING:
            title = f"Waiting: {what}"
            reason = "next in line" if running else "Obsidian is not running"
            subtitle = f"{entry.keyword}, {where(entry.target)}: {reason}"
            actions = (copy, discard)
        case State.WRITING:
            title = f"Writing: {what}"
            subtitle = "a call is in flight"
            actions = (copy,)
        case State.UNKNOWN:
            title = f"Checking: {what}"
            subtitle = entry.last_error or "checking whether it landed"
            actions = (Action(RETRY, "Retry now"), copy, discard)
        case State.FAILED:
            title = f"Not written: {what}"
            subtitle = entry.last_error or "no tries remain"
            actions = (Action(RETRY, "Retry"), copy, discard)
        case _ as unreachable:
            assert_never(unreachable)
    return Item(
        id=f"outbox:{entry.id}", title=title, subtitle=subtitle, actions=actions, icon=_OUTBOX_ICON
    )


def failure_row(error: BaseException) -> Item:
    """The one row a query that raised answers with."""
    return _say(f"vault: {type(error).__name__}: {error}")
