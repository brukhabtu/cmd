"""Find and open applications from the launcher.

No keyword: type part of an application's name and the closest matches are rows, each with
the bundle's own icon; Enter opens it. The host ranks a definite answer above every row
here, so a calculator's ``2`` still sits above an application whose name is ``1+1``.
This module is the shell: it knows where applications live and what Enter does;
``applications.scan`` finds the bundles and ``applications.matching`` ranks them.
"""

import sys
from collections.abc import Sequence
from pathlib import Path

from cmd_sdk import Description, Effect, Item, Open, PathIcon, Plugin, Show, serve
from cmd_sdk.protocol import DEFAULT_ACTION

from applications.matching import score
from applications.scan import scan

LIMIT = 8
"""How many rows to show: the closest matches, and no more than fit without scrolling."""

OPEN = "open"
"""The one action, also what Enter does."""

ROOT_FLAG = "--root"
"""Repeatable: a directory to scan instead of the defaults, so a test can supply its own."""


def _home_applications() -> tuple[Path, ...]:
    # Path.home() raises when HOME is unset and the account has no home directory; the
    # plugin then simply has no ~/Applications to scan.
    try:
        return (Path.home() / "Applications",)
    except RuntimeError:
        return ()


DEFAULT_ROOTS: tuple[Path, ...] = (
    Path("/Applications"),
    *_home_applications(),
    Path("/System/Applications"),
)
"""Where macOS keeps applications: installed, the person's own, and Apple's."""


def query(text: str, roots: Sequence[Path]) -> tuple[Item, ...]:
    """The closest matching applications under ``roots``, best first, at most ``LIMIT``."""
    scored = [(found, app) for app in scan(roots) if (found := score(text, app.name)) is not None]
    scored.sort(key=lambda pair: (-pair[0], pair[1].name.casefold(), pair[1].path))
    return tuple(
        Item(
            id=str(app.path),
            title=app.name,
            subtitle=str(app.path.parent),
            score=found,
            icon=PathIcon(str(app.path)),
        )
        for found, app in scored[:LIMIT]
    )


def run(item: str, action: str) -> Effect:
    """Open the application at ``item`` through the system, which launches or activates it.

    The target is a ``file://`` URL rather than the bare path: the host hands it to the
    system as given, and a URL without a scheme opens nothing.
    """
    if action not in {DEFAULT_ACTION, OPEN}:
        return Show(text=f"applications has no action {action!r}")
    path = Path(item)
    if not path.is_dir():
        return Show(text=f"{item} is no longer there")
    return Open(target=path.as_uri())


def roots_from_args(argv: Sequence[str]) -> tuple[Path, ...]:
    """The roots named by ``--root DIR`` arguments, or the defaults when there are none.

    Raises:
        ValueError: An argument is not a ``--root`` with a directory after it.
    """
    roots: list[Path] = []
    arguments = list(argv)
    while arguments:
        match arguments:
            case [flag, directory, *rest] if flag == ROOT_FLAG:
                roots.append(Path(directory))
                arguments = rest
            case [stray, *_]:
                raise ValueError(
                    f"unexpected argument {stray!r}; usage: applications [{ROOT_FLAG} DIR]..."
                )
    return tuple(roots) or DEFAULT_ROOTS


def plugin_for(roots: Sequence[Path]) -> Plugin:
    """The plugin with its roots fixed, so a test can point it at a tree of its own."""

    def _query(text: str) -> tuple[Item, ...]:
        return query(text, roots)

    return Plugin(Description(name="applications", version="0.1.0"), _query, run)


PLUGIN = plugin_for(DEFAULT_ROOTS)


def main() -> None:
    """Serve the plugin over stdin and stdout, scanning the roots named on the command line."""
    try:
        roots = roots_from_args(sys.argv[1:])
    except ValueError as error:
        sys.stderr.write(f"{error}\n")
        sys.exit(2)
    serve(plugin_for(roots))
