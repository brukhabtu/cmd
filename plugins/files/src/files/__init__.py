"""Find files from the launcher: ``f <part of a name>`` lists them with their folders.

Enter reveals the chosen file in Finder; the second action opens it. The search is
Spotlight's, through ``mdfind``, so it is as fresh as the index and needs no index of its
own. This module is the shell: it runs ``mdfind`` and ``open``; ``files.search`` decides
what to run and what the answer means.
"""

import shutil
from pathlib import Path

from cmd_sdk import Close, Description, Effect, Item, Open, Plugin, Show, SymbolIcon, call, serve
from cmd_sdk.protocol import DEFAULT_ACTION

from files.search import (
    OPEN,
    REVEAL,
    file_url,
    paths_from,
    rank,
    reveal_arguments,
    search_arguments,
)

SEARCH_DEADLINE = 2.0
"""Seconds to wait for mdfind: under the host's query timeout, so a slow index answers
with what it found so far instead of counting towards a hang."""

REVEAL_DEADLINE = 5.0
"""Seconds to wait for Finder: under the host's run timeout."""


def _executable(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise FileNotFoundError(f"{name} is not on PATH; the files plugin needs macOS")
    return found


_HINT = Item(
    id="",
    title="Search files by name",
    subtitle="Type part of a file name after 'f'",
    icon=SymbolIcon("magnifyingglass"),
)


def _query(text: str) -> tuple[Item, ...]:
    wanted = text.strip()
    if not wanted:
        return (_HINT,)
    mdfind = _executable("mdfind")
    found = call([mdfind, *search_arguments(wanted)], SEARCH_DEADLINE)
    return rank(paths_from(found.stdout), wanted, Path.home())


def _reveal(path: str) -> Effect:
    opener = _executable("open")
    finished = call([opener, *reveal_arguments(path)], REVEAL_DEADLINE)
    if finished.timed_out:
        return Show(text=f"Finder did not answer in time for {path}")
    if finished.returncode != 0:
        reason = finished.stderr.decode("utf-8", errors="replace").strip()
        return Show(text=f"could not reveal {path}: {reason}")
    return Close()


def _run(item: str, action: str) -> Effect:
    if not item:
        return Show(text="Type part of a file name after 'f' first")
    if action in {DEFAULT_ACTION, REVEAL}:
        return _reveal(item)
    if action == OPEN:
        return Open(target=file_url(item))
    return Show(text=f"files has no action {action!r}")


PLUGIN = Plugin(Description(name="files", version="0.1.0", keyword="f"), _query, _run)


def main() -> None:
    """Serve the plugin over stdin and stdout."""
    serve(PLUGIN)
