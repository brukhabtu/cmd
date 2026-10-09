"""The ``command`` kind: any program that takes the text as an argument and prints hits.

Decision 11. ``command`` is the program, absolute, and its arguments; no shell. In each
argument ``{text}`` becomes the typed text and ``{limit}`` the limit, and nothing else in
braces is touched, so a glob such as ``*.{md,txt}`` passes as written. ``format`` says how
stdout is read, and the order of the output is the rank.
"""

import json
import os
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cmd_sdk import CallResult

from search.hits import Failed, Found, Hit, InvalidError, Outcome, first_line, shown
from search.values import choice, program, texts

KEYS = frozenset({"command", "format", "exit_codes"})
"""The keys this kind adds to a ``[[provider]]`` table."""

REFERENCE = "Copy reference"
"""The title of the action that copies a hit's ``reference``."""

PATHS = "paths"
HITS = "hits"
FORMATS = (PATHS, HITS)

ENTRIES_PER_HIT = 4
"""How many entries the kind reads, per hit it keeps, before it stops."""

MAX_EXIT_CODE = 255

_PLACEHOLDER = re.compile(r"\{(text|limit)\}")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_HIT_FIELDS = (("snippet", str), ("reference", str))


@dataclass(frozen=True, slots=True)
class Settings:
    """A command provider's own keys."""

    program: str
    arguments: tuple[str, ...]
    format: str
    exit_codes: frozenset[int] = frozenset({0})


def parse(table: Mapping[str, Any]) -> Settings:
    """The command keys of a ``[[provider]]`` table.

    Raises:
        InvalidError: a key is wrong; the message says which.
    """
    command = texts(table, "command")
    if not command:
        raise InvalidError("command: must be set, a list: the program, then its arguments")
    executable = program(command[0], "command")
    if not any("{text}" in argument for argument in command[1:]):
        raise InvalidError("command: no argument holds {text}, so the typed text would go nowhere")
    found = choice(table.get("format"), "format", FORMATS)
    return Settings(executable, command[1:], found, _exit_codes(table.get("exit_codes", [0])))


def _exit_codes(value: object) -> frozenset[int]:
    if (
        not isinstance(value, list)
        or not value
        or not all(
            isinstance(code, int) and not isinstance(code, bool) and 0 <= code <= MAX_EXIT_CODE
            for code in value
        )
    ):
        raise InvalidError("exit_codes: must be a list of whole numbers from 0 to 255")
    return frozenset(value)


def executable(settings: Settings) -> str:
    """The program the provider runs, checked at start."""
    return settings.program


def arguments(settings: Settings, text: str, limit: int) -> tuple[str, ...]:
    """The arguments after the program, with ``{text}`` and ``{limit}`` filled, once each."""
    values = {"text": text, "limit": str(limit)}
    return tuple(
        _PLACEHOLDER.sub(lambda found: values[found[1]], argument)
        for argument in settings.arguments
    )


def scope(settings: Settings) -> str:  # ruff: ignore[unused-function-argument] - every kind's scope takes its settings
    """What the no-hits row names besides the provider: nothing, for a command."""
    return ""


def read(settings: Settings, finished: CallResult, cwd: Path, limit: int) -> Outcome:  # ruff: ignore[unused-function-argument] - every kind's read takes the working directory
    """What the command answered.

    An exit code in ``exit_codes`` is an answer. Any other is a failure, and the complete
    entries printed before it are still hits. At the deadline the complete lines are kept
    and the answer is ``cut``; a JSON array cut short is no answer.
    """
    failure = None
    if not finished.timed_out and finished.returncode not in settings.exit_codes:
        stderr = finished.stderr.decode("utf-8", "replace")
        failure = Failed(first_line(stderr, f"exited with {finished.returncode}"))
    entries = _entries(settings.format, finished)
    if isinstance(entries, Failed):
        return failure or entries
    hits: list[Hit] = []
    skipped = 0
    problem = ""
    for count, entry in enumerate(entries, 1):
        try:
            hits.append(entry())
        except InvalidError as error:
            skipped += 1
            problem = problem or str(error)
        if len(hits) == limit or count == ENTRIES_PER_HIT * limit:
            break
    if not hits and failure is not None:
        return failure
    if not hits and skipped and not finished.timed_out:
        return Failed(f"{skipped} entries are not {settings.format}: {problem}")
    return Found(
        tuple(hits), skipped=skipped, problem=problem, cut=finished.timed_out, failure=failure
    )


type _Entry = Callable[[], Hit]
"""Reading one entry: a hit, or ``InvalidError`` saying why it is none."""


def _entries(form: str, finished: CallResult) -> Iterator[_Entry] | Failed:
    stdout = finished.stdout
    if form == PATHS:
        return (_path_entry(piece) for piece in _pieces(stdout, cut=finished.timed_out))
    if stdout.lstrip().startswith(b"["):
        if finished.timed_out:
            return Failed("stopped at the deadline: half a JSON array is no answer")
        try:
            answer = json.loads(os.fsdecode(stdout))
        except ValueError as error:
            return Failed(f"answer is not a JSON array of hits: {error}")
        if not isinstance(answer, list):
            return Failed("answer is not a JSON array of hits")
        return (_hit_entry(entry) for entry in answer)
    return (_line_entry(line) for line in _pieces(stdout, cut=finished.timed_out, lines=True))


def _pieces(stdout: bytes, *, cut: bool, lines: bool = False) -> Iterator[bytes]:
    """The complete entries of the output, split by NUL if it holds one, else by line.

    After a cut call the part after the last separator is half an entry, and is dropped.

    Yields:
        Each entry that is not blank, in the order printed.
    """
    separator = b"\n" if lines or b"\0" not in stdout else b"\0"
    pieces = stdout.split(separator)
    rest = pieces.pop()
    if rest and not cut:
        pieces.append(rest)
    for piece in pieces:
        trimmed = piece.removesuffix(b"\r") if separator == b"\n" else piece
        if trimmed.strip():
            yield trimmed


def _path_entry(piece: bytes) -> _Entry:
    def entry() -> Hit:
        path = os.fsdecode(piece)
        if not path.startswith("/"):
            raise InvalidError(f"{shown(path)!r} is not an absolute path")
        return Hit(title=shown(PurePosixPath(path).name), path=path)

    return entry


def _line_entry(line: bytes) -> _Entry:
    def entry() -> Hit:
        try:
            value = json.loads(os.fsdecode(line))
        except ValueError as error:
            raise InvalidError(f"a line is not JSON: {error}") from error
        return _hit(value)

    return entry


def _hit_entry(value: object) -> _Entry:
    return lambda: _hit(value)


def _hit(value: object) -> Hit:
    """One hit as the ``hits`` format writes it.

    Raises:
        InvalidError: it is not an object with a title or an absolute path.
    """
    if not isinstance(value, dict):
        raise InvalidError("an entry is not an object")
    title = value.get("title")
    path = value.get("path")
    url = value.get("url")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise InvalidError("title: must be text")
    if path is not None and (not isinstance(path, str) or not path.startswith("/")):
        raise InvalidError(f"path: {path!r} is not an absolute path")
    if url is not None and (not isinstance(url, str) or not _SCHEME.match(url)):
        raise InvalidError(f"url: {url!r} has no scheme")
    if title is None and path is None:
        raise InvalidError("an entry has neither a title nor a path")
    line = value.get("line")
    if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
        raise InvalidError(f"line: {line!r} is not a line number")
    for key, kind in _HIT_FIELDS:
        if value.get(key) is not None and not isinstance(value.get(key), kind):
            raise InvalidError(f"{key}: must be text")
    snippet = value.get("snippet") or ""
    return Hit(
        title=shown((title or PurePosixPath(str(path)).name).strip()),
        path=path,
        url=url,
        snippet=shown(" ".join(snippet.split())),
        line=line,
        reference=value.get("reference") or None,
    )
