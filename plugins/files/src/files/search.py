"""The pure half of the files plugin: what to ask mdfind, and what to make of its answer.

Nothing here touches a process or the file system, so it is tested with strings alone.
Spotlight's own order is opaque and changes with its index, so the rows are ordered here:
how well the name matches first, then how shallow the path is, so a file at the top of the
home directory beats one buried in a build tree.
"""

from collections.abc import Sequence
from pathlib import Path

from cmd_sdk import Action, Item

LIMIT = 20
"""How many rows to show. mdfind can answer with thousands; the window shows a handful."""

REVEAL = "reveal"
OPEN = "open"

_ACTIONS = (Action(REVEAL, "Reveal in Finder"), Action(OPEN, "Open"))


def search_arguments(text: str) -> tuple[str, ...]:
    """The arguments for ``mdfind``: NUL-separated paths whose name holds ``text``."""
    return ("-0", "-name", text.strip())


def paths_from(output: bytes) -> tuple[str, ...]:
    """The paths in ``mdfind -0`` output.

    A name that is not UTF-8 is shown with replacement characters rather than dropped, so
    the person sees that the file exists even if revealing it then fails.
    """
    return tuple(part.decode("utf-8", errors="replace") for part in output.split(b"\0") if part)


def parent_folder(path: str, home: Path) -> str:
    """The folder a file sits in, with the home directory shortened to ``~``."""
    parent = Path(path).parent
    if parent == home:
        return "~"
    try:
        return f"~/{parent.relative_to(home)}"
    except ValueError:
        return str(parent)


def score(name: str, text: str) -> float:
    """How well a file name matches the typed text, case ignored.

    mdfind matches display names too, so a path can come back whose file name holds none
    of the text; it still ranks, just last.
    """
    wanted = text.strip().casefold()
    candidate = name.casefold()
    if candidate == wanted:
        return 1.0
    if candidate.startswith(wanted):
        return 0.8
    if wanted in candidate:
        return 0.6
    return 0.4


def rank(paths: Sequence[str], text: str, home: Path) -> tuple[Item, ...]:
    """The rows for a search: best match first, shallow before deep, at most ``LIMIT``."""

    def order(path: str) -> tuple[float, int, str]:
        name = Path(path).name
        return (-score(name, text), len(Path(path).parts), name.casefold())

    return tuple(
        Item(
            id=path,
            title=Path(path).name,
            subtitle=parent_folder(path, home),
            score=score(Path(path).name, text),
            actions=_ACTIONS,
        )
        for path in sorted(paths, key=order)[:LIMIT]
    )


def reveal_arguments(path: str) -> tuple[str, ...]:
    """The arguments for ``open`` that select the file in Finder instead of opening it."""
    return ("-R", path)


def file_url(path: str) -> str:
    """The ``file://`` URL for a path.

    The host hands an open target to the system as a URL, which needs a scheme and
    percent-encoding; a bare path with a space in it would not open.
    """
    return Path(path).as_uri()
