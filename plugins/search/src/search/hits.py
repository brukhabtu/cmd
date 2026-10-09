"""What a provider found: the values every kind returns and the merge reads (decision 11).

``search.kinds`` re-exports them; they live here so the kinds and ``search.kinds`` itself can
both import them without a cycle.
"""

from dataclasses import dataclass

TEXT_ERRORS = "replace"
"""How text that is not UTF-8 is decoded, where it is not a path."""


@dataclass(frozen=True, slots=True)
class Hit:
    """One thing a provider found."""

    title: str
    path: str | None = None
    """Absolute; ``None`` when the hit has no file on disk."""
    url: str | None = None
    """With a scheme, for a hit that is not a file."""
    snippet: str = ""
    """Plain text, no header line."""
    line: int | None = None
    """The 1-based line of the snippet in the file."""
    reference: str | None = None
    """The provider's own handle for the hit (qmd's docid)."""


@dataclass(frozen=True, slots=True)
class Failed:
    """The provider gave no answer the plugin can use; ``message`` is one line."""

    message: str


@dataclass(frozen=True, slots=True)
class Found:
    """What a provider answered, best first.

    ``skipped`` counts entries of the output that could not be read, and ``problem`` is the
    first of them. ``cut`` is a call stopped at the deadline: these are the hits read by
    then. ``failure`` is a command that exited with a code it does not answer with after
    printing these hits (ripgrep's exit 2 for one unreadable file): the hits still count.
    ``capped`` is a call whose output reached the size cap and was killed: these are the hits
    in the part kept.
    """

    hits: tuple[Hit, ...]
    skipped: int = 0
    problem: str = ""
    cut: bool = False
    failure: Failed | None = None
    capped: bool = False


type Outcome = Found | Failed
"""How a call went, as its kind read it."""


class InvalidError(ValueError):
    """A provider's table is wrong; the message says which key and how."""


def first_line(text: str, fallback: str) -> str:
    """The first line of ``text`` that is not blank, trimmed, or ``fallback``."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return fallback


def shown(text: str) -> str:
    """Text as a row can carry it: a character a file name smuggled in, replaced.

    A path decoded as the file system does keeps bytes that are not UTF-8 as lone
    surrogates, and so can a JSON string escape; the protocol can send neither.
    """
    try:
        raw = text.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError:
        raw = text.encode("utf-8", "surrogatepass")
    return raw.decode("utf-8", TEXT_ERRORS)
