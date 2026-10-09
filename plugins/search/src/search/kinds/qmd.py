"""The ``qmd`` kind: qmd's BM25 search through its CLI (decision 11).

The call is ``<bin> search --json --full-path -n <limit> [-c <collection>]... [--index
<index>] -- <text>``. ``--`` is always there, since a text starting with ``-`` is otherwise a
usage error, and ``--full-path`` makes qmd print each file's real path, so the plugin never
reads qmd's own config. qmd's score is ignored: the order it prints is the rank.
"""

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cmd_sdk import CallResult

from search.hits import Failed, Found, Hit, InvalidError, Outcome, first_line, shown
from search.values import choice, name, program, texts

KEYS = frozenset({"bin", "collections", "index", "mode"})
"""The keys this kind adds to a ``[[provider]]`` table."""

REFERENCE = "Copy docid"
"""The title of the action that copies a hit's docid."""

MODES = ("search",)
"""The modes this slice builds."""

SLOW_MODES = ("vsearch", "query")
"""qmd's modes that load language models in every process: refused (decision 11)."""

URI_SCHEME = "qmd://"
"""How qmd names a file it indexed and no longer finds on disk."""

ENTRIES_PER_HIT = 4
"""How many entries the kind reads, per hit it keeps, before it stops."""

_HEADER = re.compile(r"^@@ -\d+(,\d+)? @@")


@dataclass(frozen=True, slots=True)
class Settings:
    """A qmd provider's own keys."""

    bin: str
    collections: tuple[str, ...] = ()
    index: str | None = None


def parse(table: Mapping[str, Any]) -> Settings:
    """The qmd keys of a ``[[provider]]`` table.

    Raises:
        InvalidError: a key is wrong; the message says which.
    """
    executable = program(table.get("bin"), "bin")
    collections = texts(table, "collections")
    for collection in collections:
        if not collection.strip() or collection.startswith("-"):
            raise InvalidError(f"collections: {collection!r} is not a collection's name")
    index = table.get("index")
    if index is not None:
        index = name(index, "index")
    mode = table.get("mode", "search")
    if mode in SLOW_MODES:
        raise InvalidError(
            f'mode: "{mode}" loads language models on every search, which decision 11 keeps'
            ' off the query path; use "search"'
        )
    choice(mode, "mode", MODES)
    return Settings(bin=executable, collections=collections, index=index)


def executable(settings: Settings) -> str:
    """The program the provider runs, checked at start."""
    return settings.bin


def arguments(settings: Settings, text: str, limit: int) -> tuple[str, ...]:
    """The arguments after the program."""
    collections = tuple(word for collection in settings.collections for word in ("-c", collection))
    index = ("--index", settings.index) if settings.index is not None else ()
    return ("search", "--json", "--full-path", "-n", str(limit), *collections, *index, "--", text)


def scope(settings: Settings) -> str:
    """What the no-hits row names besides the provider: the index, when one is set."""
    return f"index {settings.index}" if settings.index is not None else ""


def read(settings: Settings, finished: CallResult, cwd: Path, limit: int) -> Outcome:  # ruff: ignore[unused-function-argument] - every kind's read takes its settings
    """What qmd answered.

    ``cwd`` is qmd's working directory, the plugin's own, which a ``./`` path is under.
    """
    if finished.timed_out:
        return Failed("no answer by the deadline: half a JSON array is no answer")
    if finished.truncated:
        return Failed("printed more than the plugin reads: half a JSON array is no answer")
    if finished.returncode != 0:
        stderr = finished.stderr.decode("utf-8", "replace")
        return Failed(first_line(stderr, f"exited with {finished.returncode}"))
    try:
        answer = json.loads(os.fsdecode(finished.stdout))
    except ValueError as error:
        return Failed(f"answer is not qmd's JSON: {error}")
    if not isinstance(answer, list):
        return Failed("answer is not qmd's JSON: not an array")
    hits: list[Hit] = []
    skipped = 0
    problem = ""
    for entry in answer[: ENTRIES_PER_HIT * limit]:
        try:
            hits.append(_hit(entry, cwd))
        except InvalidError as error:
            skipped += 1
            problem = problem or str(error)
            continue
        if len(hits) == limit:
            break
    return Found(tuple(hits), skipped=skipped, problem=problem)


def _hit(entry: object, cwd: Path) -> Hit:
    """One element of qmd's array.

    Raises:
        InvalidError: it is not an object with a file qmd could have printed.
    """
    if not isinstance(entry, dict):
        raise InvalidError("an entry is not an object")
    file = entry.get("file")
    if not isinstance(file, str) or not file:
        raise InvalidError("an entry has no file")
    path = url = None
    if file.startswith("/"):
        path = file
    elif file.startswith("./"):
        path = str(cwd / file.removeprefix("./"))
    elif file.startswith(URI_SCHEME):
        url = file
    else:
        raise InvalidError(f"file {shown(file)!r} is neither a path nor a qmd:// URI")
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        title = PurePosixPath(file).name
    title = shown(title.strip())
    snippet = entry.get("snippet")
    line = entry.get("line")
    docid = entry.get("docid")
    return Hit(
        title=title,
        path=path,
        url=url,
        snippet=shown(clean_snippet(snippet, title)) if isinstance(snippet, str) else "",
        line=line if isinstance(line, int) and not isinstance(line, bool) and line >= 1 else None,
        reference=docid if isinstance(docid, str) and docid else None,
    )


def clean_snippet(snippet: str, title: str) -> str:
    """A snippet as a row shows it.

    Its first line goes when it is qmd's diff-style header (``@@ -1,3 @@ (...)``), a line
    ``# <title>`` and blank lines go, and whitespace collapses to single spaces.
    """
    lines = snippet.splitlines()
    if lines and _HEADER.match(lines[0]):
        lines = lines[1:]
    heading = f"# {title.strip()}"
    kept = [line for line in lines if line.strip() and line.strip() != heading]
    return " ".join(" ".join(kept).split())
