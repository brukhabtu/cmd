"""The pure half of ``query`` and ``run`` beyond the merge: routing, the plugin's own rows, ids.

The plugin declares no keyword (decision 11, as decision 10 until draft 5), so it sees
nearly every keystroke: ``route`` answers ``None`` for text whose first word is none of its
keywords, and the shell returns no rows at once, with no process, no file read and no lock.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from cmd_sdk import Item, SymbolIcon

from search.merge import PROBLEM_ICON, Report, Target, decode, summary
from search.schema import Problem, Provider, Settings, fold

STATUS = "status"
HINT = "hint:min"
NONE = "none"
CONFIG = "config:"
PROBLEM = "problem:"
PROVIDER = "provider:"

_STATUS_ICON = SymbolIcon("magnifyingglass.circle")


@dataclass(frozen=True, slots=True)
class Startup:
    """How the start went: the settings, every problem in them, and where the config goes."""

    settings: Settings
    config_directory: str | None = None


# --- which keyword ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Status:
    """The status keyword: every provider, its last outcome, every config problem."""


@dataclass(frozen=True, slots=True)
class Keyword:
    """A provider keyword: the providers it selects, the text after it, its problems.

    ``problems`` pairs each config problem on this keyword with its place in the list,
    which is its row's id.
    """

    typed: str
    text: str
    providers: tuple[Provider, ...]
    problems: tuple[tuple[int, Problem], ...]


type Route = Status | Keyword


def route(text: str, settings: Settings) -> Route | None:
    """Which of the plugin's keywords starts ``text``, ASCII case ignored; ``None`` if none."""
    parts = text.split(maxsplit=1)
    if not parts:
        return None
    word = fold(parts[0])
    if word == fold(settings.status_keyword):
        return Status()
    providers = tuple(provider for provider in settings.providers if provider.answers(word))
    problems = tuple(
        (position, problem)
        for position, problem in enumerate(settings.problems)
        if word in problem.keywords
    )
    if not providers and not problems:
        return None
    rest = parts[1].strip() if len(parts) > 1 else ""
    return Keyword(parts[0], rest, providers, problems)


# --- the plugin's own rows ------------------------------------------------------------------


def config_rows(problems: tuple[tuple[int, Problem], ...]) -> tuple[Item, ...]:
    """Each config problem as its row; Enter opens the config directory."""
    return tuple(
        Item(
            id=f"{CONFIG}{position}",
            title=problem.message,
            subtitle="Enter opens the config directory",
            icon=PROBLEM_ICON,
        )
        for position, problem in problems
    )


def hint_row(found: Keyword, min_chars: int) -> Item:
    """The row for a text too short to search: what would be searched, and what to type."""
    names = ", ".join(provider.name for provider in found.providers if provider.unusable is None)
    return Item(
        id=HINT,
        title=f"Search {names}",
        subtitle=f"Type at least {min_chars} characters after {found.typed}",
        icon=SymbolIcon("magnifyingglass"),
    )


def status_rows(startup: Startup, last: Mapping[str, Report]) -> tuple[Item, ...]:
    """The status keyword: a summary, each provider with its last outcome, every problem."""
    settings = startup.settings
    keywords = settings.keywords()[1:]
    count = len(settings.providers)
    rows = [
        Item(
            id=STATUS,
            title=f"search: {count} provider{'s' if count != 1 else ''}",
            subtitle=f"keywords: {', '.join(keywords)}" if keywords else "nothing to search yet",
            icon=_STATUS_ICON,
        )
    ]
    rows += [
        Item(
            id=f"{PROVIDER}{provider.name}",
            title=f"{provider.name}: {provider.kind} on {', '.join(provider.keywords)}",
            subtitle=provider.unusable
            or summary(provider, last.get(provider.name), settings.deadline),
            icon=_STATUS_ICON,
        )
        for provider in settings.providers
    ]
    rows += config_rows(tuple(enumerate(settings.problems)))
    return tuple(rows)


def failure_row(error: BaseException) -> Item:
    """The one row a query that raised answers with."""
    return Item(
        id=f"{PROBLEM}search", title=f"search: {type(error).__name__}: {error}", icon=PROBLEM_ICON
    )


# --- what an id means -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OnHit:
    """An action on a hit."""

    target: Target


@dataclass(frozen=True, slots=True)
class OpenConfig:
    """Enter on a config problem: open the config directory, made first if missing."""


@dataclass(frozen=True, slots=True)
class Detail:
    """Enter on a provider's row or its problem: show its last command and stderr."""

    provider: str


@dataclass(frozen=True, slots=True)
class Say:
    """Enter on a row that only informs: keep the launcher open and say this."""

    text: str


type Choice = OnHit | OpenConfig | Detail | Say


def choice(item: str) -> Choice:  # ruff: ignore[too-many-return-statements] - one return per kind of id
    """What a row's id asks ``run`` to do. An id this plugin did not make says so."""
    if item.startswith("{"):
        target = decode(item)
        return OnHit(target) if target is not None else Say(f"search made no row {item!r}")
    if item.startswith(CONFIG):
        return OpenConfig()
    for prefix in (PROBLEM, PROVIDER):
        if item.startswith(prefix):
            return Detail(item.removeprefix(prefix))
    if item == HINT:
        return Say("Type a few more characters to search")
    if item == NONE:
        return Say("Nothing matched; try other words")
    if item == STATUS:
        return Say("Each provider and every config problem is listed below")
    return Say(f"search made no row {item!r}")
