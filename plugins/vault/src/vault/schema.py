"""The pure half of the config: what a parsed ``config.toml`` means (decision 10).

``parse`` takes the dict the SDK's ``config()`` returned and gives back ``Settings``: what
works, and every problem found, each aimed at the keyword it belongs to. A problem never
stops what still works: a bad capture is dropped and the rest are kept, a bad deadline
falls back to its default. Nothing here touches the file system; whether ``obsidian.bin``
is an executable file is the shell's question.
"""

import string
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

DAILY = "@daily"
"""The target that means today's daily note."""

DEFAULT_STATUS_KEYWORD = "vault"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M"
DEFAULT_APP = "/Applications/Obsidian.app"
DEFAULT_PROCESS = "Obsidian"  # [2.4] what `pgrep -x` sees for a running Obsidian
DEFAULT_LINE = "- {text}"
DEFAULT_LIMIT = 20
MAX_LIMIT = 50

PROBE_AND_QUERY_LIMIT = 1.8
"""Seconds the probe and a view's call may take together: with the call's 1 s grace for
pipes, they stay under the host's 3 s query timeout."""

# Characters Obsidian refuses in a file name, which `{text}` loses inside a path.
_REFUSED_IN_NAMES = str.maketrans(dict.fromkeys('\\/:*?"<>|#^[]', ""))


class CaptureKind(StrEnum):
    """What a capture does: add a line to a note, or create a note and open it."""

    APPEND = "append"
    OPEN = "open"


class ViewKind(StrEnum):
    """What a view lists: notes matching the text, or open tasks matching it."""

    SEARCH = "search"
    TASKS = "tasks"


BUILT_CAPTURES = frozenset({CaptureKind.APPEND})
"""The capture kinds this slice builds; the schema accepts the others and says so."""

BUILT_VIEWS = frozenset({ViewKind.SEARCH})
"""The view kinds this slice builds."""


@dataclass(frozen=True, slots=True)
class Deadlines:
    """Seconds each kind of call to the CLI may take (decision 10's table)."""

    probe: float = 0.3
    query: float = 1.5  # [2.4]
    write: float = 5.0  # [2.4]
    run: float = 2.0


@dataclass(frozen=True, slots=True)
class Obsidian:
    """How to reach Obsidian. ``bin`` is ``None`` when the config gave no usable one."""

    bin: str | None
    app: str = DEFAULT_APP
    process: str = DEFAULT_PROCESS
    vault: str | None = None
    deadlines: Deadlines = Deadlines()


@dataclass(frozen=True, slots=True)
class Capture:
    """One ``[[capture]]``: a keyword that writes what follows it into a note."""

    keyword: str
    kind: CaptureKind
    target: str
    template: str | None = None
    heading: str | None = None
    line: str = DEFAULT_LINE


@dataclass(frozen=True, slots=True)
class View:
    """One ``[[view]]``: a keyword that lists what the vault holds."""

    keyword: str
    kind: ViewKind
    limit: int = DEFAULT_LIMIT


@dataclass(frozen=True, slots=True)
class Problem:
    """Something wrong with the config, and where the person sees it.

    ``keyword`` is the capture or view it belongs to, or ``None`` for the status keyword
    alone. ``everywhere`` puts it on every keyword, for a problem that stops every write.
    """

    message: str
    keyword: str | None = None
    everywhere: bool = False


@dataclass(frozen=True, slots=True)
class Settings:
    """The config as the plugin uses it, with what was wrong with it."""

    status_keyword: str = DEFAULT_STATUS_KEYWORD
    date_format: str = DEFAULT_DATE_FORMAT
    time_format: str = DEFAULT_TIME_FORMAT
    obsidian: Obsidian = Obsidian(bin=None)
    captures: tuple[Capture, ...] = ()
    views: tuple[View, ...] = ()
    problems: tuple[Problem, ...] = ()

    def keywords(self) -> tuple[str, ...]:
        """Every keyword this config answers, the status keyword first."""
        return (
            self.status_keyword,
            *(capture.keyword for capture in self.captures),
            *(view.keyword for view in self.views),
        )


class _InvalidError(ValueError):
    """One entry or value is wrong; the message says how. Caught inside ``parse``."""


_TOP = frozenset({"status_keyword", "date_format", "time_format", "obsidian", "capture", "view"})
_OBSIDIAN = frozenset({"bin", "app", "process", "vault", "deadlines"})
_DEADLINES = frozenset({"probe", "query", "write", "run"})
_CAPTURE = frozenset({"keyword", "kind", "target", "template", "heading", "line"})
_VIEW = frozenset({"keyword", "kind", "limit"})
_DEADLINE_MAXIMUM = {"write": 30.0, "run": 8.0}


def fold(word: str) -> str:
    """A keyword as the host compares it: ASCII letters lower-cased, anything else as is."""
    return word.translate(_ASCII_LOWER)


_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def _placeholders(template: str, key: str) -> frozenset[str]:
    """The ``{names}`` a template uses.

    Raises:
        _InvalidError: a brace is unbalanced, or a placeholder carries a format or a conversion.
    """
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as error:
        raise _InvalidError(f"{key}: {template!r}: {error}") from error
    names = set()
    for _, name, spec, conversion in parsed:
        if name is None:
            continue
        if spec or conversion:
            raise _InvalidError(f"{key}: {template!r}: a placeholder takes no format")
        names.add(name)
    return frozenset(names)


def safe_in_path(text: str) -> str:
    """``{text}`` as it goes into a path.

    It loses the characters Obsidian refuses in a file name, and its outer spaces.
    """
    return text.translate(_REFUSED_IN_NAMES).strip()


def parse(raw: Mapping[str, Any]) -> Settings:
    """What a parsed ``config.toml`` means. Never raises: every problem is in ``problems``.

    An empty dict is no config at all, which the shell reports on its own; it is parsed
    here like any other, as a config with nothing to capture.
    """
    problems: list[Problem] = [
        Problem(f"{key}: not a key this config has") for key in sorted(raw.keys() - _TOP)
    ]
    status_keyword = _top_word(raw, "status_keyword", DEFAULT_STATUS_KEYWORD, problems)
    date_format = _top_text(raw, "date_format", DEFAULT_DATE_FORMAT, problems)
    time_format = _top_text(raw, "time_format", DEFAULT_TIME_FORMAT, problems)
    obsidian = _obsidian(raw.get("obsidian"), problems)
    taken = {fold(status_keyword)}
    captures = _entries(raw, "capture", _capture, taken, problems)
    views = _entries(raw, "view", _view, taken, problems)
    if "capture" not in raw and "view" not in raw:
        problems.append(Problem("the config has no [[capture]] and no [[view]]"))
    return Settings(
        status_keyword=status_keyword,
        date_format=date_format,
        time_format=time_format,
        obsidian=obsidian,
        captures=captures,
        views=views,
        problems=tuple(problems),
    )


def without_bin(settings: Settings, problem: str) -> Settings:
    """The settings with ``obsidian.bin`` refused, and the problem shown on every keyword."""
    return replace(
        settings,
        obsidian=replace(settings.obsidian, bin=None),
        problems=(*settings.problems, Problem(problem, everywhere=True)),
    )


# --- the top level -----------------------------------------------------------------------


def _top_text(raw: Mapping[str, Any], key: str, default: str, problems: list[Problem]) -> str:
    value = raw.get(key, default)
    if isinstance(value, str) and value:
        return value
    problems.append(Problem(f"{key}: must be text; using {default!r}"))
    return default


def _top_word(raw: Mapping[str, Any], key: str, default: str, problems: list[Problem]) -> str:
    value = _top_text(raw, key, default, problems)
    if _is_word(value):
        return value
    problems.append(Problem(f"{key}: must be one word; using {default!r}"))
    return default


def _is_word(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value.split()) == 1
        and value == value.strip()
    )


def _tables(
    raw: Mapping[str, Any], key: str, problems: list[Problem]
) -> tuple[Mapping[str, Any], ...]:
    value = raw.get(key, [])
    if isinstance(value, list) and all(isinstance(entry, dict) for entry in value):
        return tuple(value)
    problems.append(Problem(f"{key}: must be an array of tables, [[{key}]]"))
    return ()


# --- [obsidian] --------------------------------------------------------------------------


def _obsidian(value: object, problems: list[Problem]) -> Obsidian:
    if value is None:
        problems.append(
            Problem("obsidian.bin: must be set, to the CLI's absolute path", everywhere=True)
        )
        return Obsidian(bin=None)
    if not isinstance(value, dict):
        problems.append(Problem("obsidian: must be a table, [obsidian]", everywhere=True))
        return Obsidian(bin=None)
    problems += [
        Problem(f"obsidian.{key}: not a key this config has")
        for key in sorted(value.keys() - _OBSIDIAN)
    ]
    executable = value.get("bin")
    if not isinstance(executable, str) or not PurePosixPath(executable).is_absolute():
        shown = "must be set" if executable is None else f"{executable!r} is not an absolute path"
        problems.append(Problem(f"obsidian.bin: {shown}", everywhere=True))
        executable = None
    app = value.get("app", DEFAULT_APP)
    if not isinstance(app, str) or not PurePosixPath(app).is_absolute():
        problems.append(Problem(f"obsidian.app: must be an absolute path; using {DEFAULT_APP}"))
        app = DEFAULT_APP
    process = value.get("process", DEFAULT_PROCESS)
    if not isinstance(process, str) or not process:
        problems.append(Problem(f"obsidian.process: must be text; using {DEFAULT_PROCESS!r}"))
        process = DEFAULT_PROCESS
    vault = value.get("vault")
    if vault is not None and (not isinstance(vault, str) or not vault):
        problems.append(Problem("obsidian.vault: must be a vault's name; using the CLI's default"))
        vault = None
    return Obsidian(
        bin=executable,
        app=app,
        process=process,
        vault=vault,
        deadlines=_deadlines(value.get("deadlines", {}), problems),
    )


def _deadlines(value: object, problems: list[Problem]) -> Deadlines:
    defaults = Deadlines()
    if not isinstance(value, dict):
        problems.append(Problem("obsidian.deadlines: must be a table; using the defaults"))
        return defaults
    problems += [
        Problem(f"obsidian.deadlines.{key}: not a key this config has")
        for key in sorted(value.keys() - _DEADLINES)
    ]
    chosen = {
        name: _seconds(value.get(name), name, getattr(defaults, name), problems)
        for name in sorted(_DEADLINES)
    }
    if chosen["probe"] + chosen["query"] > PROBE_AND_QUERY_LIMIT:
        for name in ("query", "probe"):
            if chosen["probe"] + chosen["query"] > PROBE_AND_QUERY_LIMIT:
                problems.append(
                    Problem(
                        f"obsidian.deadlines: probe + query must be at most "
                        f"{PROBE_AND_QUERY_LIMIT} s; {name} uses {getattr(defaults, name)} s"
                    )
                )
                chosen[name] = getattr(defaults, name)
    return Deadlines(**chosen)


def _seconds(value: object, name: str, default: float, problems: list[Problem]) -> float:
    if value is None:
        return default
    maximum = _DEADLINE_MAXIMUM.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        problems.append(
            Problem(f"obsidian.deadlines.{name}: must be seconds above 0; using {default}")
        )
        return default
    if maximum is not None and value > maximum:
        problems.append(
            Problem(f"obsidian.deadlines.{name}: must be at most {maximum} s; using {default}")
        )
        return default
    return float(value)


# --- [[capture]] and [[view]] --------------------------------------------------------------


def _entries[T](
    raw: Mapping[str, Any],
    table: str,
    build: Callable[[Mapping[str, Any], str], T],
    taken: set[str],
    problems: list[Problem],
) -> tuple[T, ...]:
    """Each valid entry of ``[[table]]``; an invalid one is dropped with its problem."""
    found: list[T] = []
    for entry in _tables(raw, table, problems):
        try:
            keyword = _claim(entry, table, taken)
            found.append(build(entry, keyword))
        except _InvalidError as error:
            named = entry.get("keyword") if _is_word(entry.get("keyword")) else None
            label = named or f"a [[{table}]]"
            problems.append(Problem(f"{label}: {error}", keyword=named))
            continue
        taken.add(fold(keyword))
    return tuple(found)


def _claim(entry: Mapping[str, Any], table: str, taken: set[str]) -> str:
    """The entry's keyword, if it is one word, not taken, and the entry has no unknown key.

    Raises:
        _InvalidError: it is not.
    """
    keyword = entry.get("keyword")
    if not isinstance(keyword, str) or not _is_word(keyword):
        raise _InvalidError("keyword: must be one word")
    if fold(keyword) in taken:
        raise _InvalidError("keyword: already used by another entry")
    if unknown := sorted(entry.keys() - (_CAPTURE if table == "capture" else _VIEW)):
        raise _InvalidError(f"{', '.join(unknown)}: not a key a [[{table}]] has")
    return keyword


def _capture(entry: Mapping[str, Any], keyword: str) -> Capture:
    """One capture.

    Raises:
        _InvalidError: a value is wrong; the message says which.
    """
    kind = _choice(entry.get("kind"), CaptureKind, "kind")
    target = entry.get("target")
    if not isinstance(target, str) or not target:
        raise _InvalidError("target: must be set")
    template = _optional_text(entry, "template")
    heading = _optional_text(entry, "heading")
    _check_target(entry, kind, target, template)
    if heading is not None and heading.startswith("#"):
        raise _InvalidError("heading: the heading's text, without #")
    line = entry.get("line", DEFAULT_LINE)
    _check_line(line)
    return Capture(keyword, kind, target, template, heading, line)


def _check_target(
    entry: Mapping[str, Any], kind: CaptureKind, target: str, template: str | None
) -> None:
    """Refuse a target, or a key, the kind does not allow.

    Raises:
        _InvalidError: the kind does not allow it.
    """
    if kind is CaptureKind.OPEN:
        if target == DAILY:
            raise _InvalidError(f'target: {DAILY} is for kind = "append" only')
        if used := sorted(entry.keys() & {"heading", "line"}):
            raise _InvalidError(f'{used[0]}: is for kind = "append" only')
    if target != DAILY:
        _check_path(target)
    elif template is not None:
        raise _InvalidError(f"template: not with {DAILY}, which uses the Daily notes template")


def _check_line(line: object) -> None:
    """Refuse a line that is not one line holding ``{text}``.

    Raises:
        _InvalidError: it is not.
    """
    if not isinstance(line, str) or "\n" in line:
        raise _InvalidError("line: must be one line of text")
    used = _placeholders(line, "line")
    if "text" not in used:
        raise _InvalidError("line: must contain {text}")
    if unknown := used - {"text", "date", "time"}:
        raise _InvalidError(f"line: unknown placeholder {{{min(unknown)}}}")


def _view(entry: Mapping[str, Any], keyword: str) -> View:
    kind = _choice(entry.get("kind"), ViewKind, "kind")
    limit = entry.get("limit", DEFAULT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise _InvalidError(f"limit: must be a whole number from 1 to {MAX_LIMIT}")
    return View(keyword, kind, limit)


def _choice[K: StrEnum](value: object, kinds: type[K], key: str) -> K:
    for kind in kinds:
        if value == kind.value:
            return kind
    names = " or ".join(f'"{kind.value}"' for kind in kinds)
    raise _InvalidError(f"{key}: must be {names}")


def _optional_text(entry: Mapping[str, Any], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value or "\n" in value:
        raise _InvalidError(f"{key}: must be one line of text")
    return value


def _check_path(target: str) -> None:
    path = PurePosixPath(target)
    if path.is_absolute() or ".." in path.parts:
        raise _InvalidError(f"target: {target!r} must be {DAILY} or a path inside the vault")
    if not target.endswith(".md"):
        raise _InvalidError(f"target: {target!r} must end in .md")
    if unknown := _placeholders(target, "target") - {"text", "date"}:
        raise _InvalidError(f"target: unknown placeholder {{{min(unknown)}}}")
