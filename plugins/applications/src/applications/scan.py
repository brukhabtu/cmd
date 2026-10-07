"""Which applications are installed: the ``.app`` bundles under a few roots.

Pure apart from reading directories, and it imports nothing of ours. A bundle's title is
its directory name without the suffix; Finder sometimes shows a localised display name
from the bundle's Info.plist instead, which is a later refinement if anyone minds.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

BUNDLE_SUFFIX = ".app"

DEPTH = 2
"""How many directory levels below a root are searched.

Apple keeps Terminal and its siblings in /System/Applications/Utilities, one folder down,
and nothing anyone launches sits deeper than that. A bundle holds bundles of its own
(helpers, under Contents) that must not be listed, so a bundle is never descended into.
"""


@dataclass(frozen=True)
class App:
    """One application bundle: its title and where it is."""

    name: str
    path: Path


def scan(roots: Iterable[Path], depth: int = DEPTH) -> tuple[App, ...]:
    """Every bundle under ``roots``, each at most ``depth`` levels down, sorted by name.

    A root that is missing or cannot be read is skipped in silence: not every Mac has a
    ``~/Applications``, and the plugin should answer with what the other roots hold.
    """
    found = {app.path: app for root in roots for app in _bundles_under(root, depth)}
    return tuple(sorted(found.values(), key=lambda app: (app.name.casefold(), app.path)))


def _bundles_under(directory: Path, depth: int) -> Iterator[App]:
    if depth <= 0:
        return
    try:
        children = list(directory.iterdir())
    except OSError:
        return
    for child in children:
        if not child.is_dir():
            continue
        if child.suffix == BUNDLE_SUFFIX:
            yield App(name=child.stem, path=child)
        else:
            yield from _bundles_under(child, depth - 1)
