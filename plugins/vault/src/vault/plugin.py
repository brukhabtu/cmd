"""The shell of the vault plugin: start, ``query``, ``run`` and ``main``.

Decision 10. ``start`` reads the config once and the outbox from the data directory;
``query`` answers from them, the probe and, for a search, the CLI, and never raises;
``run`` queues a capture and returns; the outbox thread does the writing.
"""

import json
import os
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from functools import partial
from pathlib import Path

from cmd_sdk import (
    Close,
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
from cmd_sdk.locate import CONFIG_FILE, CONFIG_VARIABLE, directory_from
from cmd_sdk.protocol import DEFAULT_ACTION

from vault.answers import (
    COPY,
    DISCARD,
    RETRY,
    Hits,
    Misconfigured,
    NotRunning,
    OnEntry,
    OpenApp,
    OpenConfig,
    OpenNote,
    Queue,
    Say,
    Searched,
    Startup,
    Status,
    ToCapture,
    ToView,
    Unanswered,
    Unbuilt,
    capture_rows,
    choice,
    entry_row,
    everywhere_rows,
    failure_row,
    outbox_rows,
    problem_rows,
    route,
    status_rows,
    view_rows,
)
from vault.gateway import Running, Searches, invoke, probe
from vault.invocations import found_paths, open_arguments, search_arguments
from vault.outbox import (
    Answered,
    Refused,
    TimedOut,
    capture_time,
    copied,
    new_entry,
    retried,
)
from vault.schema import BUILT_CAPTURES, Settings, parse, without_bin
from vault.store import BusyError, Outbox
from vault.worker import Worker, World

KEYWORDS_FILE = "keywords.json"
"""The keywords of the last config that parsed, in the data directory."""

OUTBOX_DIRECTORY = "outbox"

DESCRIPTION = Description(name="vault", version="0.1.0")
"""No keyword: the plugin matches its own, which come from the config (decision 10)."""


@dataclass(frozen=True, slots=True)
class Vault:
    """Everything ``query`` and ``run`` work from, made once by ``start``."""

    startup: Startup
    outbox: Outbox
    world: World
    searches: Searches


def now() -> datetime:
    """The local time, with its offset, as an entry records it."""
    return datetime.now().astimezone()


def start(
    ask: Callable[[], bool] | None = None,
    clock: Callable[[], datetime] = now,
    ticks: Callable[[], float] = time.monotonic,
) -> Vault:
    """Read the config and the outbox. Never raises: what went wrong becomes rows.

    ``ask`` is whether Obsidian runs; it defaults to ``pgrep -x`` on the configured process
    name, and a test passes its own. ``clock`` is the time entries record, ``ticks`` the one
    the caches age by; a test passes both.
    """
    problems: list[str] = []
    data = _data_directory(problems)
    startup = _startup(data, problems)
    if data is None:
        startup = replace(startup, settings=replace(startup.settings, captures=()))
        outbox = Outbox(None)
    else:
        try:
            outbox, unread = Outbox.load(data / OUTBOX_DIRECTORY)
        except OSError as error:
            problems.append(f"outbox: {error}; {data} cannot hold it, so nothing is captured")
            startup = replace(startup, settings=replace(startup.settings, captures=()))
            outbox, unread = Outbox(None), ()
        problems += unread
    startup = replace(startup, problems=(*startup.problems, *problems))
    obsidian = startup.settings.obsidian
    if ask is None:
        ask = partial(probe, obsidian.process, obsidian.deadlines.probe)
    world = World(obsidian=obsidian, running=Running(ask, ticks), clock=clock)
    return Vault(startup=startup, outbox=outbox, world=world, searches=Searches(ticks))


def _data_directory(problems: list[str]) -> Path | None:
    try:
        return data_dir()
    except MissingVariableError as error:
        problems.append(str(error))
        return None


def _startup(data: Path | None, problems: list[str]) -> Startup:
    """The config as the plugin will use it, and what was wrong with reading it."""
    try:
        directory = str(directory_from(os.environ, CONFIG_VARIABLE))
    except MissingVariableError as error:
        problems.append(str(error))
        return Startup(Settings())
    try:
        raw = config()
    except ConfigError as error:
        return Startup(
            Settings(),
            config_directory=directory,
            unreadable=str(error),
            stale_keywords=_stale_keywords(data),
        )
    except OSError as error:
        # The SDK raises ConfigError for these from task 2.6 on; an older one lets them by.
        return Startup(
            Settings(),
            config_directory=directory,
            unreadable=f"{directory}/{CONFIG_FILE} cannot be read: {error}",
            stale_keywords=_stale_keywords(data),
        )
    if not raw:
        return Startup(Settings(), config_directory=directory, no_config=True)
    settings = parse(raw)
    executable = settings.obsidian.bin
    if executable is not None and not (
        Path(executable).is_file() and os.access(executable, os.X_OK)
    ):
        settings = without_bin(settings, f"obsidian.bin: {executable} is not an executable file")
    if data is not None:
        _keep_keywords(data, settings)
    return Startup(settings, config_directory=directory)


def _keep_keywords(data: Path, settings: Settings) -> None:
    try:
        (data / KEYWORDS_FILE).write_text(json.dumps(list(settings.keywords())), encoding="utf-8")
    except OSError as error:
        sys.stderr.write(f"vault: cannot keep {KEYWORDS_FILE}: {error}\n")


def _stale_keywords(data: Path | None) -> tuple[str, ...]:
    if data is None:
        return ()
    try:
        kept = json.loads((data / KEYWORDS_FILE).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return ()
    if not isinstance(kept, list):
        return ()
    return tuple(word for word in kept if isinstance(word, str))


# --- query --------------------------------------------------------------------------------


def query(vault: Vault, text: str) -> tuple[Item, ...]:
    """The rows for ``text``. Never raises: an exception becomes one row, and goes to stderr."""
    try:
        return _query(vault, text)
    except Exception as error:  # ruff: ignore[blind-except] - decision 10: query never raises
        sys.stderr.write(f"vault: query {text!r}: {type(error).__name__}: {error}\n")
        return (failure_row(error),)


def _query(vault: Vault, text: str) -> tuple[Item, ...]:
    found = route(text, vault.startup)
    if found is None:
        return ()
    settings = vault.startup.settings
    running = vault.world.running()
    entries = vault.outbox.entries()
    match found:
        case Status():
            return status_rows(vault.startup, entries, settings.time_format, running=running)
        case ToCapture():
            rows = capture_rows(found, settings, vault.world.clock(), running=running)
            rows += everywhere_rows(settings)
        case ToView():
            rows = view_rows(found, _search(vault, found, running=running))
            rows += everywhere_rows(settings)
        case Unbuilt() | Misconfigured():
            rows = problem_rows(found)
    return rows + outbox_rows(
        entries, settings.status_keyword, settings.time_format, running=running
    )


def _search(vault: Vault, found: ToView, *, running: bool) -> Searched | None:  # ruff: ignore[too-many-return-statements] - one return per answer
    """What the CLI's search answered, called only when Obsidian runs."""
    if not found.text:
        return None
    obsidian = vault.world.obsidian
    if obsidian.bin is None:
        return Unanswered("Search needs a usable obsidian.bin")
    if not running:
        return NotRunning()
    key = (found.view.keyword, found.text)
    kept = vault.searches.get(key)
    if kept is not None:
        return Hits(kept)
    deadline = obsidian.deadlines.query
    match invoke(search_arguments(obsidian, found.text, found.view.limit), deadline):
        case Answered() as answered:
            paths = found_paths(answered.stdout, found.view.limit)
            vault.searches.put(key, paths)
            return Hits(paths)
        case Refused() as refused:
            return Unanswered(refused.error)
        case TimedOut():
            return Unanswered(f"Obsidian did not answer within {deadline} s")


# --- run ----------------------------------------------------------------------------------


def run(vault: Vault, item: str, action: str) -> Effect:
    """What Enter on a row does. A capture is queued and the launcher closes at once."""
    match choice(item):
        case Queue() as queued:
            return _queue(vault, queued)
        case Say() as said:
            return Show(text=said.text)
        case OnEntry() as on_entry:
            return _on_entry(vault, on_entry.entry_id, action)
        case OpenNote() as note:
            return _open_note(vault, note.path)
        case OpenApp():
            return Open(target=Path(vault.world.obsidian.app).as_uri())
        case OpenConfig():
            return _open_config(vault)


def _queue(vault: Vault, queued: Queue) -> Effect:
    settings = vault.startup.settings
    captures = [
        capture
        for capture in settings.captures
        if capture.keyword == queued.keyword and capture.kind in BUILT_CAPTURES
    ]
    if not captures:
        return Show(text=f"vault has no capture {queued.keyword!r}")
    if not queued.text.strip():
        return Show(text=f"Type the text after {queued.keyword}")
    entry = new_entry(
        captures[0],
        queued.text,
        capture_time(vault.world.clock(), vault.outbox.entries()),
        secrets.token_hex(3),
        (settings.date_format, settings.time_format),
    )
    try:
        vault.outbox.add(entry)
    except OSError as error:
        return Show(text=f"Could not keep the capture ({error}); it was: {entry.line}")
    return Close()


def _on_entry(vault: Vault, entry_id: str, action: str) -> Effect:  # ruff: ignore[too-many-return-statements] - one return per action
    entry = vault.outbox.get(entry_id)
    if entry is None:
        return Show(text="That entry is gone: written or discarded")
    if action == DEFAULT_ACTION:
        running = vault.world.running()
        actions = entry_row(entry, vault.startup.settings.time_format, running=running).actions
        action = actions[0].id
    try:
        if action == COPY:
            return Copy(text=copied(entry))
        if action == RETRY:
            vault.outbox.update(retried(entry, vault.world.clock()), unless_writing=True)
            return Close()
        if action == DISCARD:
            vault.outbox.remove(entry_id, unless_writing=True)
            return Close()
    except BusyError:
        return Show(text="It is being written now; look again in a moment")
    except OSError as error:
        return Show(text=f"The outbox could not be changed: {error}")
    return Show(text=f"vault has no action {action!r}")


def _open_note(vault: Vault, path: str) -> Effect:
    obsidian = vault.world.obsidian
    if obsidian.bin is None:
        return Show(text="Opening a note needs a usable obsidian.bin")
    match invoke(open_arguments(obsidian, path), obsidian.deadlines.run):
        case Answered():
            return Close()
        case Refused() as refused:
            return Show(text=f"Could not open {path}: {refused.error}")
        case TimedOut():
            return Show(text=f"Obsidian did not open {path} within {obsidian.deadlines.run} s")


def _open_config(vault: Vault) -> Effect:
    directory = vault.startup.config_directory
    if directory is None:
        return Show(text="The host did not say where the config goes")
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return Show(text=f"Could not make {directory}: {error}")
    return Open(target=Path(directory).as_uri())


# --- main ---------------------------------------------------------------------------------


def plugin(vault: Vault) -> Plugin:
    """The plugin over a started vault."""
    return Plugin(DESCRIPTION, partial(query, vault), partial(run, vault))


def main() -> None:
    """Start, start the outbox thread, and serve over stdin and stdout."""
    vault = start()
    Worker(vault.outbox, vault.world).start()
    serve(plugin(vault))
