"""The pure half of talking to the obsidian CLI: which arguments to pass, what the answer means.

Every command and parameter name here is a guess until task 2.4's spike runs the real CLI
on the owner's Mac, and they are all in this one module so the spike's answers change one
file. Each guess is marked [2.4]. The guesses: a call names its vault with a leading
``vault=<name>``; parameters are ``key=value`` words; a note is named by its vault-relative
``path=``; ``daily:append`` makes today's daily note when it is missing; ``append`` takes
``heading=``; ``search`` prints one vault-relative path per line; errors arrive on stderr,
and a missing note's error says "not found" or "does not exist".
"""

import re
from collections.abc import Sequence

from vault.outbox import Entry, Step
from vault.schema import DAILY, Obsidian

_MISSING = re.compile(r"not found|does not exist|no such", re.IGNORECASE)  # [2.4]


def _base(obsidian: Obsidian) -> list[str]:
    """The executable, and the vault when the config names one [2.4].

    Raises:
        ValueError: the settings have no usable ``bin``; the shell never calls then.
    """
    if obsidian.bin is None:  # pragma: no cover - the shell never calls without one
        raise ValueError("obsidian.bin is not set")
    head = [obsidian.bin]
    if obsidian.vault is not None:
        head.append(f"vault={obsidian.vault}")
    return head


def write_arguments(obsidian: Obsidian, entry: Entry, step: Step) -> list[str]:
    """The arguments for one call of a try at writing ``entry`` [2.4]."""
    daily = entry.target == DAILY
    match step:
        case Step.READ:
            tail = ["daily:read"] if daily else ["read", f"path={entry.target}"]
        case Step.CREATE:
            tail = ["create", f"path={entry.target}"]
            if entry.template is not None:
                tail.append(f"template={entry.template}")
        case Step.APPEND:
            tail = ["daily:append"] if daily else ["append", f"path={entry.target}"]
            tail.append(f"content={entry.line}")
            if entry.heading is not None:
                tail.append(f"heading={entry.heading}")
    return [*_base(obsidian), *tail]


def search_arguments(obsidian: Obsidian, text: str, limit: int) -> list[str]:
    """The arguments that search the vault for ``text`` [2.4]."""
    return [*_base(obsidian), "search", f"query={text}", f"limit={limit}"]


def open_arguments(obsidian: Obsidian, path: str) -> list[str]:
    """The arguments that open a note in Obsidian [2.4]."""
    return [*_base(obsidian), "open", f"path={path}"]


def probe_arguments(process: str) -> list[str]:
    """``pgrep -x``: exit 0 when a process of exactly that name runs [2.4] (the name)."""
    return ["/usr/bin/pgrep", "-x", process]


def found_paths(stdout: str, limit: int) -> tuple[str, ...]:
    """The notes a search printed, one path a line, blanks dropped, at most ``limit`` [2.4]."""
    paths = (line.strip() for line in stdout.splitlines())
    return tuple(path for path in paths if path)[:limit]


def first_line(stderr: str, fallback: str) -> str:
    """The first line of what the CLI said on stderr, or ``fallback`` when it said nothing."""
    for line in stderr.splitlines():
        if line.strip():
            return line.strip()
    return fallback


def says_missing(stderr: str) -> bool:
    """Whether the CLI's error says the note does not exist [2.4]."""
    return _MISSING.search(stderr) is not None


def note_name(path: str) -> str:
    """A note's name as a row shows it: the file name without ``.md``."""
    name = path.rsplit("/", 1)[-1]
    return name.removesuffix(".md")


def folder(path: str) -> str:
    """The folder a note sits in, or "the vault's top" for one at the top."""
    head, _, _ = path.rpartition("/")
    return head or "the vault's top folder"


def joined(arguments: Sequence[str]) -> str:
    """The arguments as one line, for a log on stderr."""
    return " ".join(arguments)
