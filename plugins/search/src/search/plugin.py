"""The shell of the search plugin: start, ``query``, ``run`` and ``main``.

Decision 11. ``start`` reads the config once and checks each provider's program. ``query``
routes the text, starts one daemon thread per selected provider that is neither cached nor
resting, waits for them until ``deadline + GRACE`` seconds after it began, and merges what
came back; it never raises. ``run`` acts on a row from its id alone.
"""

import json
import os
import shlex
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

from cmd_sdk import (
    CallResult,
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
    call,
    config,
    data_dir,
    serve,
)
from cmd_sdk.locate import CONFIG_FILE, CONFIG_VARIABLE, directory_from
from cmd_sdk.protocol import DEFAULT_ACTION

from search.hits import Failed, Found, Outcome, shown
from search.kinds import KINDS
from search.memory import REST_AFTER, Memory
from search.merge import (
    COPY_PATH,
    COPY_REFERENCE,
    COPY_TEXT,
    COPY_URI,
    COPY_URL,
    OPEN,
    REVEAL,
    Called,
    Report,
    Resting,
    Target,
    Unanswered,
    Unstarted,
    actions,
    rows,
)
from search.replies import (
    Detail,
    Keyword,
    OnHit,
    OpenConfig,
    Say,
    Startup,
    Status,
    bad_text_row,
    choice,
    config_rows,
    failure_row,
    hint_row,
    route,
    status_rows,
)
from search.settings import Problem, Provider, Settings, command_line, fold, parse, unusable

GRACE = 1.0
"""Seconds ``call`` may wait, after a child exits, for pipes a grandchild holds open."""

MAX_OUTPUT = 1 << 20
"""Bytes of a provider's output the plugin keeps, per stream; past it the provider is killed."""

REVEAL_DEADLINE = 5.0
"""Seconds to wait for Finder, as the files plugin does."""

OPENER = "/usr/bin/open"
KEYWORDS_FILE = "keywords.json"
"""The keywords of the last config that parsed, in the data directory."""

DESCRIPTION = Description(name="search", version="0.1.0")
"""No keyword: the plugin matches its own, which come from the config (decision 11)."""

type Runner = Callable[[Sequence[str], float], CallResult]
"""How a command is run: the SDK's ``call``, killing what it started at the deadline."""


@dataclass(frozen=True, slots=True)
class Search:
    """Everything ``query`` and ``run`` work from, made once by ``start``."""

    startup: Startup
    memory: Memory
    runner: Runner
    clock: Callable[[], datetime]
    cwd: Callable[[], Path]
    home: str
    opener: str = OPENER


def _call(command: Sequence[str], deadline: float) -> CallResult:
    return call(command, deadline, kill_on_timeout=True, max_output=MAX_OUTPUT)


def now() -> datetime:
    """The local time, which the rest's "until 14:31" is told in."""
    return datetime.now().astimezone()


def start(  # ruff: ignore[too-many-arguments] - each is a boundary a test fakes
    *,
    runner: Runner = _call,
    clock: Callable[[], datetime] = now,
    ticks: Callable[[], float] = time.monotonic,
    cwd: Callable[[], Path] = Path.cwd,
    home: str | None = None,
    opener: str = OPENER,
) -> Search:
    """Read the config and check each provider's program. Never raises: problems become rows."""
    try:
        startup = _startup()
    except Exception as error:  # ruff: ignore[blind-except] - a start that fails is a row, not a dead plugin
        sys.stderr.write(f"search: start: {type(error).__name__}: {error}\n")
        startup = Startup(Settings(problems=(Problem(f"search could not start: {error}"),)))
    return Search(
        startup=startup,
        memory=Memory(ticks),
        runner=runner,
        clock=clock,
        cwd=cwd,
        home=home if home is not None else str(Path("~").expanduser()),
        opener=opener,
    )


def _startup() -> Startup:
    try:
        directory = str(directory_from(os.environ, CONFIG_VARIABLE))
    except MissingVariableError as error:
        return Startup(Settings(problems=(Problem(str(error)),)))
    try:
        data = data_dir()
    except MissingVariableError as error:
        return Startup(Settings(problems=(Problem(str(error)),)), directory)
    try:
        raw = config()
    except ConfigError as error:
        return _unreadable(str(error), data, directory)
    except OSError as error:
        return _unreadable(f"{directory}/{CONFIG_FILE} cannot be read: {error}", data, directory)
    if not raw:
        message = f"No config: create {CONFIG_FILE} in {directory}"
        return Startup(Settings(problems=(Problem(message),)), directory)
    settings = parse(raw)
    for provider in settings.providers:
        executable = KINDS[provider.kind].executable(provider.settings)
        if not (Path(executable).is_file() and os.access(executable, os.X_OK)):
            message = f"{provider.name}: {executable} is not an executable file"
            settings = unusable(settings, provider.name, message)
    _keep_keywords(data, settings)
    return Startup(settings, directory)


def _unreadable(message: str, data: Path, directory: str) -> Startup:
    stale = _stale_keywords(data)
    problem = Problem(f"{message}; nothing is searched until it is fixed", stale)
    return Startup(Settings(problems=(problem,)), directory)


def _keep_keywords(data: Path, settings: Settings) -> None:
    try:
        (data / KEYWORDS_FILE).write_text(json.dumps(list(settings.keywords())), encoding="utf-8")
    except OSError as error:
        sys.stderr.write(f"search: cannot keep {KEYWORDS_FILE}: {error}\n")


def _stale_keywords(data: Path) -> tuple[str, ...]:
    try:
        kept = json.loads((data / KEYWORDS_FILE).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return ()
    if not isinstance(kept, list):
        return ()
    return tuple(fold(word) for word in kept if isinstance(word, str))


# --- query --------------------------------------------------------------------------------


def query(search: Search, text: str) -> tuple[Item, ...]:
    """The rows for ``text``. Never raises: an exception becomes one row, and goes to stderr."""
    try:
        return _query(search, text)
    except Exception as error:  # ruff: ignore[blind-except] - decision 11: query never raises
        sys.stderr.write(f"search: query {text!r}: {type(error).__name__}: {error}\n")
        return (failure_row(error),)


def _query(search: Search, text: str) -> tuple[Item, ...]:
    settings = search.startup.settings
    found = route(text, settings)
    match found:
        case None:
            return ()
        case Status():
            return status_rows(search.startup, search.memory.reports())
        case Keyword():
            problems = config_rows(found.problems)
            usable = tuple(provider for provider in found.providers if provider.unusable is None)
            if not usable:
                return problems
            if len(found.text) < settings.min_chars:
                return (hint_row(found, settings.min_chars), *problems)
            if "\0" in found.text:
                return (bad_text_row(), *problems)
            answers = _ask(search, usable, found.text)
            return (*rows(answers, settings.deadline, search.home), *problems)


def _ask(
    search: Search, providers: tuple[Provider, ...], text: str
) -> tuple[tuple[Provider, Report], ...]:
    """Each provider's report: from the cache, resting, or a call on its own thread.

    The threads are waited for until ``deadline + GRACE`` seconds after this began; one still
    running then did not answer, and whatever it brings later is not in this answer.
    """
    ends = time.monotonic() + search.startup.settings.deadline + GRACE
    lock = threading.Lock()
    reports: dict[str, Report] = {}
    threads = []
    for provider in providers:
        resting = search.memory.resting(provider.name)
        kept = search.memory.cached(provider.name, text) if resting is None else None
        if resting is not None:
            until = (search.clock() + timedelta(seconds=resting)).strftime("%H:%M")
            kept = Resting(until, REST_AFTER)
        if kept is not None:
            with lock:
                reports[provider.name] = kept
            continue
        thread = threading.Thread(
            target=_search, args=(search, provider, text, reports, lock), daemon=True
        )
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join(max(0.0, ends - time.monotonic()))
    with lock:
        return tuple((provider, reports.get(provider.name, Unanswered())) for provider in providers)


def _search(
    search: Search, provider: Provider, text: str, reports: dict[str, Report], lock: threading.Lock
) -> None:
    """One provider's call, on its own thread. Never raises: a failure is its report."""
    try:
        report, stderr = _called(search, provider, text)
    except Exception as error:  # ruff: ignore[blind-except] - a thread's failure is its provider's row
        report, stderr = Unstarted(f"{type(error).__name__}: {error}"), ""
    search.memory.record(provider.name, text, report, stderr)
    with lock:
        reports[provider.name] = report


def _called(search: Search, provider: Provider, text: str) -> tuple[Report, str]:
    command = command_line(provider, text)
    search.memory.started(provider.name, shlex.join(command))
    kind = KINDS[provider.kind]
    try:
        finished = search.runner(command, search.startup.settings.deadline)
    except OSError as error:
        program = kind.executable(provider.settings)
        return Unstarted(f"cannot run {program}: {error.strerror or error}"), ""
    try:
        outcome = kind.read(provider.settings, finished, search.cwd(), provider.limit)
    except Exception as error:  # ruff: ignore[blind-except] - decision 11: a kind's exception is Failed
        outcome = Failed(f"{type(error).__name__}: {error}")
    report = Called(outcome, finished.returncode, finished.timed_out, real_paths(outcome))
    return report, finished.stderr.decode("utf-8", "replace")


def real_paths(outcome: Outcome) -> tuple[str | None, ...]:
    """Each hit's real path, resolved in the provider's own thread, so the deadline covers it.

    ``os.path.realpath`` reads only the file system's metadata. A path it cannot resolve is
    ``None``, and is compared as written.
    """
    if not isinstance(outcome, Found):
        return ()
    keys: list[str | None] = []
    for hit in outcome.hits:
        try:
            keys.append(os.path.realpath(hit.path) if hit.path is not None else None)
        except OSError, ValueError:
            keys.append(None)
    return tuple(keys)


# --- run ----------------------------------------------------------------------------------


def run(search: Search, item: str, action: str) -> Effect:
    """What Enter, or another action, does on a row."""
    match choice(item):
        case OnHit() as on_hit:
            return _on_hit(search, on_hit.target, action)
        case OpenConfig():
            return _open_config(search)
        case Detail() as detail:
            return _detail(search, detail.provider)
        case Say() as said:
            return Show(text=said.text)


def _on_hit(search: Search, target: Target, action: str) -> Effect:
    if action == DEFAULT_ACTION:
        action = actions(target, "")[0].id
    if action in {OPEN, REVEAL} and target.path is not None and not Path(target.path).exists():
        return Show(text=_gone(search, target))
    effect = _effect(search, target, action)
    return effect or Show(text=f"search has no action {action!r} for this row")


def _effect(search: Search, target: Target, action: str) -> Effect | None:  # ruff: ignore[too-many-return-statements] - one return per action
    path, url = target.path, target.url
    if action == OPEN and path is not None and target.open is not None:
        return Open(target=target.open)
    if action == OPEN and url is not None and not target.not_on_disk:
        return Open(target=url)
    if action == REVEAL and path is not None:
        return _reveal(search, path)
    if action == COPY_PATH and path is not None:
        return Copy(text=shown(path))
    if action == COPY_REFERENCE and target.reference is not None:
        return Copy(text=target.reference)
    if action in {COPY_URL, COPY_URI} and url is not None:
        return Copy(text=url)
    if action == COPY_TEXT:
        return Copy(text=target.title)
    return None


def _gone(search: Search, target: Target) -> str:
    message = f"{shown(target.path or '')} is not there any more"
    kinds = {
        provider.kind
        for provider in search.startup.settings.providers
        if provider.name in target.by
    }
    return f"{message}; run qmd update" if "qmd" in kinds else message


def _reveal(search: Search, path: str) -> Effect:
    try:
        finished = call([search.opener, "-R", path], REVEAL_DEADLINE)
    except OSError as error:
        return Show(text=f"could not reveal {shown(path)}: {error.strerror or error}")
    if finished.timed_out:
        return Show(text=f"Finder did not answer in time for {shown(path)}")
    if finished.returncode != 0:
        reason = finished.stderr.decode("utf-8", errors="replace").strip()
        return Show(text=f"could not reveal {shown(path)}: {reason}")
    return Close()


def _open_config(search: Search) -> Effect:
    directory = search.startup.config_directory
    if directory is None:
        return Show(text="The host did not say where the config goes")
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return Show(text=f"Could not make {directory}: {error}")
    return Open(target=Path(directory).as_uri())


def _detail(search: Search, provider: str) -> Effect:
    last = search.memory.last(provider)
    if last is None:
        return Show(text=f"{provider} has not been searched since the plugin started")
    stderr = last.stderr or "(nothing on stderr)"
    return Show(text=f"{last.command}\n{stderr}")


# --- main ---------------------------------------------------------------------------------


def plugin(search: Search) -> Plugin:
    """The plugin over a started search."""
    return Plugin(DESCRIPTION, partial(query, search), partial(run, search))


def main() -> None:
    """Start, and serve over stdin and stdout."""
    serve(plugin(start()))
