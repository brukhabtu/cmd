"""The pure half of the config: what a parsed ``config.toml`` means (decision 11).

``parse`` takes the dict the SDK's ``config()`` returned and gives back ``Settings``: the
providers that work, and every problem found, each aimed at the keywords it belongs to. A
problem never stops what still works: an invalid provider is dropped and the rest are kept,
an out-of-range number falls back to its default. Nothing here touches the file system;
whether a provider's program is an executable file is the shell's question.
"""

import os
import re
import string
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import quote

from search.hits import InvalidError
from search.kinds import KINDS
from search.values import choice, is_word, name

DEFAULT_STATUS_KEYWORD = "search"
DEFAULT_DEADLINE = 1.0
DEADLINE_RANGE = (0.5, 1.5)
"""Seconds. With ``call``'s 1 s grace for pipes the wait stays inside the host's 3 s."""
DEFAULT_MIN_CHARS = 2
MIN_CHARS_RANGE = (1, 10)
DEFAULT_LIMIT = 10
MAX_LIMIT = 50
DEFAULT_OPEN = "{uri}"
LONGEST_NAME = 32

ENV = "/usr/bin/env"
"""How a provider's ``env`` reaches its program: ``/usr/bin/env K=V ... <program>``."""

_TOP = frozenset({"status_keyword", "deadline", "min_chars", "provider"})
_COMMON = frozenset({"name", "kind", "keywords", "env", "limit", "open"})
_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_OPEN_PLACEHOLDER = re.compile(r"\{(uri|path|line)\}")
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def fold(word: str) -> str:
    """A keyword as the host compares it: ASCII letters lower-cased, anything else as is."""
    return word.translate(_ASCII_LOWER)


@dataclass(frozen=True, slots=True)
class Problem:
    """Something wrong with the config. It shows on the status keyword and on ``keywords``.

    ``keywords`` are folded: the keywords of the provider it belongs to, when they parsed.
    """

    message: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Provider:
    """One ``[[provider]]``, checked. ``settings`` is its kind's own, which its kind made.

    ``unusable`` is set by the shell when the program is not an executable file: the
    provider is kept, so its keywords still answer, and nothing is started for it.
    """

    name: str
    kind: str
    keywords: tuple[str, ...]
    settings: Any
    env: tuple[tuple[str, str], ...] = ()
    limit: int = DEFAULT_LIMIT
    open: str = DEFAULT_OPEN
    reference: str = "Copy reference"
    """The title of the action that copies a hit's reference, from its kind."""
    scope: str = ""
    """What the no-hits row names besides the provider, from its kind."""
    unusable: str | None = None

    def answers(self, word: str) -> bool:
        """Whether this provider is selected by ``word``, ASCII case ignored."""
        return fold(word) in {fold(keyword) for keyword in self.keywords}


@dataclass(frozen=True, slots=True)
class Settings:
    """The config as the plugin uses it, with what was wrong with it."""

    status_keyword: str = DEFAULT_STATUS_KEYWORD
    deadline: float = DEFAULT_DEADLINE
    min_chars: int = DEFAULT_MIN_CHARS
    providers: tuple[Provider, ...] = ()
    problems: tuple[Problem, ...] = ()

    def keywords(self) -> tuple[str, ...]:
        """Every keyword this config answers, folded, the status keyword first."""
        found = [fold(self.status_keyword)]
        found += [fold(word) for provider in self.providers for word in provider.keywords]
        found += [word for problem in self.problems for word in problem.keywords]
        return tuple(dict.fromkeys(found))


def parse(raw: Mapping[str, Any]) -> Settings:
    """What a parsed ``config.toml`` means. Never raises: every problem is in ``problems``."""
    problems = [Problem(f"{key}: not a key this config has") for key in sorted(raw.keys() - _TOP)]
    status_keyword = _status_keyword(raw.get("status_keyword"), problems)
    deadline = _deadline(raw.get("deadline"), problems)
    min_chars = _min_chars(raw.get("min_chars"), problems)
    providers: list[Provider] = []
    for position, table in enumerate(_tables(raw, problems), 1):
        try:
            providers.append(_provider(table, status_keyword, providers))
        except InvalidError as error:
            label = table.get("name") if is_word(table.get("name")) else f"provider {position}"
            problems.append(Problem(f"{label}: {error}", _keywords_anyway(table)))
    return Settings(status_keyword, deadline, min_chars, tuple(providers), tuple(problems))


def unusable(settings: Settings, provider_name: str, message: str) -> Settings:
    """The settings with one provider's program refused: kept, called never, the problem shown."""
    providers = []
    problems = list(settings.problems)
    for provider in settings.providers:
        if provider.name != provider_name:
            providers.append(provider)
            continue
        providers.append(replace(provider, unusable=message))
        problems.append(Problem(message, tuple(fold(word) for word in provider.keywords)))
    return replace(settings, providers=tuple(providers), problems=tuple(problems))


def command_line(provider: Provider, text: str) -> tuple[str, ...]:
    """The argv for a search: the program and its arguments, through ``env`` when it has one."""
    kind = KINDS[provider.kind]
    called: tuple[str, ...] = (kind.executable(provider.settings),)
    called += kind.arguments(provider.settings, text, provider.limit)
    if not provider.env:
        return called
    return (ENV, *(f"{key}={value}" for key, value in provider.env), *called)


def file_url(path: str) -> str:
    """The ``file://`` URL of an absolute path, percent-encoded but for ``/``."""
    return "file://" + quote(os.fsencode(path), safe="/")


def fill_open(template: str, path: str, line: int | None) -> str:
    """What Enter opens for a hit with a path: each placeholder filled once, in one pass."""
    values = {
        "uri": file_url(path),
        "path": quote(os.fsencode(path), safe="/"),
        "line": str(line or 1),
    }
    return _OPEN_PLACEHOLDER.sub(lambda found: values[found[1]], template)


# --- the top level -----------------------------------------------------------------------


def _status_keyword(value: object, problems: list[Problem]) -> str:
    if value is None:
        return DEFAULT_STATUS_KEYWORD
    if is_word(value) and isinstance(value, str):
        return value
    problems.append(Problem(f"status_keyword: must be one word; using {DEFAULT_STATUS_KEYWORD!r}"))
    return DEFAULT_STATUS_KEYWORD


def _deadline(value: object, problems: list[Problem]) -> float:
    if value is None:
        return DEFAULT_DEADLINE
    low, high = DEADLINE_RANGE
    if isinstance(value, int | float) and not isinstance(value, bool) and low <= value <= high:
        return float(value)
    problems.append(
        Problem(f"deadline: must be seconds from {low} to {high}; using {DEFAULT_DEADLINE}")
    )
    return DEFAULT_DEADLINE


def _min_chars(value: object, problems: list[Problem]) -> int:
    if value is None:
        return DEFAULT_MIN_CHARS
    low, high = MIN_CHARS_RANGE
    if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
        return value
    problems.append(
        Problem(
            f"min_chars: must be a whole number from {low} to {high}; using {DEFAULT_MIN_CHARS}"
        )
    )
    return DEFAULT_MIN_CHARS


def _tables(raw: Mapping[str, Any], problems: list[Problem]) -> tuple[Mapping[str, Any], ...]:
    value = raw.get("provider")
    if value is None:
        problems.append(Problem("no [[provider]]: add one to config.toml"))
        return ()
    if isinstance(value, list) and all(isinstance(table, dict) for table in value):
        return tuple(value)
    problems.append(Problem("provider: must be an array of tables, [[provider]]"))
    return ()


# --- [[provider]] --------------------------------------------------------------------------


def _provider(table: Mapping[str, Any], status_keyword: str, earlier: list[Provider]) -> Provider:
    """One provider, checked.

    Raises:
        InvalidError: something in it is wrong; the message says what.
    """
    called = name(table.get("name"), "name", LONGEST_NAME)
    if fold(called) in {fold(provider.name) for provider in earlier}:
        raise InvalidError("name: another provider has it")
    kind_name = choice(table.get("kind"), "kind", tuple(KINDS))
    kind = KINDS[kind_name]
    if unknown := sorted(table.keys() - _COMMON - kind.KEYS):
        raise InvalidError(f"{', '.join(unknown)}: not a key a {kind_name} provider has")
    keywords = _keywords(table.get("keywords"), status_keyword)
    env = _env(table.get("env"))
    limit = table.get("limit", DEFAULT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise InvalidError(f"limit: must be a whole number from 1 to {MAX_LIMIT}")
    opens = _open(table.get("open", DEFAULT_OPEN))
    settings = kind.parse(table)
    return Provider(
        name=called,
        kind=kind_name,
        keywords=keywords,
        settings=settings,
        env=env,
        limit=limit,
        open=opens,
        reference=kind.REFERENCE,
        scope=kind.scope(settings),
    )


def _keywords(value: object, status_keyword: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(is_word(word) for word in value):
        raise InvalidError(
            "keywords: must be a list of one or more words; a provider with none would run"
            " on every keystroke"
        )
    words = tuple(dict.fromkeys(str(word) for word in value))
    for word in words:
        if fold(word) == fold(status_keyword):
            raise InvalidError(f"keywords: {word!r} is the status keyword")
    return words


def _keywords_anyway(table: Mapping[str, Any]) -> tuple[str, ...]:
    """The keywords of a provider that is invalid, when they parsed, so its problem shows."""
    value = table.get("keywords")
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(fold(word) for word in value if is_word(word)))


def _env(value: object) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise InvalidError('env: must be a table of text, such as { PATH = "/usr/bin:/bin" }')
    for key, text in value.items():
        if not _VARIABLE.fullmatch(key):
            raise InvalidError(f"env: {key!r} is not a variable's name")
        if not isinstance(text, str) or "\0" in text:
            raise InvalidError(f"env.{key}: must be text")
    return tuple(value.items())


def _open(value: object) -> str:
    if not isinstance(value, str) or ("{uri}" not in value and "{path}" not in value):
        raise InvalidError("open: must be text holding {uri} or {path}")
    if not _SCHEME.match(fill_open(value, "/a", 1)):
        raise InvalidError('open: must be a URL with a scheme once filled; "{uri}" opens the file')
    return value
