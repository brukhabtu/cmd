"""The pure half of a search: what each provider's answer becomes, merged into rows.

Decision 11. Rank, never score: every provider's first hit, in config order, then every
second hit, and so on. Two hits are one when their files are the same (by the real path the
shell resolved in time, else the path as written) or their URLs are; the row keeps the best
rank's title, snippet and ``open``, the reference from whichever has one, and names every
provider. After the hits come the problem rows, one per provider, so a failing, slow or
resting provider never hides the others' hits.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from cmd_sdk import Action, Icon, Item, PathIcon, SymbolIcon

from search.hits import Failed, Found, Hit, Outcome, shown
from search.kinds.qmd import URI_SCHEME
from search.settings import Provider, fill_open

OPEN = "open"
REVEAL = "reveal"
COPY_PATH = "copy-path"
COPY_REFERENCE = "copy-reference"
COPY_URL = "copy-url"
COPY_URI = "copy-uri"
COPY_TEXT = "copy-text"

NOT_ON_PATH = (126, 127)
"""Exit codes that mean a program could not be found or run: ``env``'s, a shell's."""

PROBLEM_ICON = SymbolIcon("exclamationmark.triangle")


# --- what the shell hands over ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Called:
    """The call came back, by its deadline or killed at it.

    ``keys`` are each hit's real path, as resolved in time, or ``None`` where it was not.
    """

    outcome: Outcome
    returncode: int | None
    timed_out: bool
    keys: tuple[str | None, ...] = ()


@dataclass(frozen=True, slots=True)
class Unstarted:
    """The program would not start (``OSError``), or the call itself raised."""

    message: str


@dataclass(frozen=True, slots=True)
class Unanswered:
    """The provider's thread was still running when ``query`` stopped waiting."""


@dataclass(frozen=True, slots=True)
class Resting:
    """The provider missed its last ``slow`` deadlines and starts nothing until ``until``."""

    until: str
    slow: int


type Report = Called | Unstarted | Unanswered | Resting
"""What became of one provider in one search."""


# --- what an id carries --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Target:
    """What ``run`` needs for a hit, carried in its id, so ``run`` keeps no memory."""

    title: str
    by: tuple[str, ...]
    at: int
    path: str | None = None
    open: str | None = None
    url: str | None = None
    reference: str | None = None

    @property
    def not_on_disk(self) -> bool:
        """A qmd hit for a file qmd indexed and no longer finds."""
        return self.path is None and self.url is not None and self.url.startswith(URI_SCHEME)


def encode(target: Target) -> str:
    """A hit's id: a small JSON object. ASCII, so a path that is not UTF-8 survives it."""
    fields: dict[str, Any] = {"title": target.title, "by": list(target.by), "at": target.at}
    for key in ("path", "open", "url", "reference"):
        value = getattr(target, key)
        if value is not None:
            fields[key] = value
    return json.dumps(fields, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def decode(item: str) -> Target | None:
    """The target an id names, or ``None`` when it is not one this plugin made."""
    try:
        fields = json.loads(item)
        by = tuple(str(name) for name in fields["by"])
        target = Target(title=str(fields["title"]), by=by, at=int(fields["at"]))
        texts = {key: fields.get(key) for key in ("path", "open", "url", "reference")}
    except ValueError, KeyError, TypeError:
        return None
    if not all(value is None or isinstance(value, str) for value in texts.values()):
        return None
    return Target(target.title, target.by, target.at, **texts)


def actions(target: Target, reference_title: str) -> tuple[Action, ...]:
    """What a hit's row offers, Enter first, by its shape (decision 11's table)."""
    reference = (Action(COPY_REFERENCE, reference_title),) if target.reference else ()
    if target.path is not None:
        return (
            Action(OPEN, "Open"),
            Action(REVEAL, "Reveal in Finder"),
            Action(COPY_PATH, "Copy path"),
            *reference,
        )
    if target.not_on_disk:
        return (*reference, Action(COPY_URI, "Copy qmd URI"))
    if target.url is not None:
        return (Action(OPEN, "Open"), Action(COPY_URL, "Copy URL"))
    return (Action(COPY_TEXT, "Copy text"),)


# --- merging -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Merged:
    """One row's hit: the best-ranked provider's hit, with every provider that found it."""

    hit: Hit
    by: tuple[str, ...]
    open: str
    reference: str | None
    reference_title: str


def _hits(report: Report) -> tuple[tuple[Hit, str | None], ...]:
    if not isinstance(report, Called) or not isinstance(report.outcome, Found):
        return ()
    keys = report.keys + (None,) * (len(report.outcome.hits) - len(report.keys))
    return tuple(zip(report.outcome.hits, keys, strict=False))


def _identity(hit: Hit, key: str | None) -> tuple[str, str] | None:
    if hit.path is not None:
        return ("path", key or hit.path)
    if hit.url is not None:
        return ("url", hit.url)
    return None


def interleave(answers: Sequence[tuple[Provider, Report]]) -> tuple[Merged, ...]:
    """Every provider's hits merged by rank, config order breaking ties, duplicates collapsed."""
    found = [(provider, _hits(report)) for provider, report in answers]
    merged: list[Merged] = []
    seen: dict[tuple[str, str], int] = {}
    for rank in range(max((len(hits) for _, hits in found), default=0)):
        for provider, hits in found:
            if rank >= len(hits):
                continue
            hit, key = hits[rank]
            identity = _identity(hit, key)
            if identity is None or identity not in seen:
                if identity is not None:
                    seen[identity] = len(merged)
                merged.append(
                    Merged(hit, (provider.name,), provider.open, hit.reference, provider.reference)
                )
                continue
            first = merged[seen[identity]]
            by = first.by if provider.name in first.by else (*first.by, provider.name)
            reference, title = first.reference, first.reference_title
            if reference is None and hit.reference is not None:
                reference, title = hit.reference, provider.reference
            merged[seen[identity]] = Merged(first.hit, by, first.open, reference, title)
    return tuple(merged)


# --- the rows ------------------------------------------------------------------------------


def folder(path: str, home: str) -> str:
    """The folder a file sits in, with the home directory shortened to ``~``."""
    parent = str(PurePosixPath(path).parent)
    if parent == home:
        return "~"
    if home not in {"", "/"} and parent.startswith(home + "/"):
        return "~" + parent.removeprefix(home)
    return parent


def _icon(merged: Merged, target: Target) -> Icon:
    if target.path is not None:
        try:
            target.path.encode("utf-8")
        except UnicodeEncodeError:
            return SymbolIcon("doc")
        return PathIcon(target.path)
    if target.not_on_disk:
        return SymbolIcon("questionmark.folder")
    if merged.hit.url is not None:
        return SymbolIcon("link")
    return SymbolIcon("doc.text")


def _subtitle(merged: Merged, target: Target, home: str) -> str:
    names = ", ".join(merged.by)
    hit = merged.hit
    if target.path is not None:
        return f"{names}: {hit.snippet or shown(folder(target.path, home))}"
    if target.not_on_disk:
        return f"{names}: not on disk since qmd last indexed it; run qmd update"
    if hit.url is not None:
        return f"{names}: {shown(hit.url)}"
    return f"{names}: {hit.snippet}" if hit.snippet else names


def hit_row(merged: Merged, position: int, home: str) -> Item:
    """One merged hit as its row. ``position`` is its place in the merged order."""
    hit = merged.hit
    target = Target(
        title=hit.title,
        by=merged.by,
        at=position,
        path=hit.path,
        open=fill_open(merged.open, hit.path, hit.line) if hit.path is not None else None,
        url=hit.url,
        reference=merged.reference,
    )
    return Item(
        id=encode(target),
        title=hit.title,
        subtitle=_subtitle(merged, target, home),
        actions=actions(target, merged.reference_title),
        icon=_icon(merged, target),
    )


def _exit(returncode: int | None) -> str:
    if returncode in NOT_ON_PATH:
        return "a program it needs is not on its PATH: set env.PATH"
    if returncode == 0:
        return "exit 0"
    return f"exit {returncode}; check this provider in config.toml"


def _late(name: str, deadline: float) -> tuple[str, str]:
    return (
        f"{name} did not answer within {deadline} s",
        "its hits are left out; the others' are above",
    )


def tidy(text: str, limit: int = 160) -> str:
    """``text`` safe for a row: control characters shown as ``?``, and at most ``limit`` long."""
    shown = "".join(char if char.isprintable() else "?" for char in text)
    return shown if len(shown) <= limit else shown[: limit - 1] + "\u2026"


def problem(provider: Provider, report: Report, deadline: float) -> tuple[str, str] | None:
    """The title and subtitle of a provider's problem row, or ``None`` when it has none."""
    found = _problem(provider, report, deadline)
    return None if found is None else (tidy(found[0]), tidy(found[1]))


def _problem(provider: Provider, report: Report, deadline: float) -> tuple[str, str] | None:
    name = provider.name
    match report:
        case Resting():
            title = f"{name} is resting after {report.slow} slow answers, until {report.until}"
            return (title, "its hits are left out")
        case Unstarted():
            return (f"{name}: {report.message}", "check its program in config.toml")
        case Called(outcome=Failed() as failed) if not report.timed_out:
            return (f"{name}: {failed.message}", _exit(report.returncode))
        case Called(outcome=Found() as found) if (
            found.failure or found.cut or found.capped or found.skipped
        ):
            return _found_problem(name, found, report.returncode, deadline)
        case Called(outcome=Found()):
            return None
        case _:
            # Unanswered, or an answer that could not be read by the deadline.
            return _late(name, deadline)


def _found_problem(
    name: str, found: Found, returncode: int | None, deadline: float
) -> tuple[str, str]:
    """The problem row of an answer that still holds hits: a failure, a cut, skipped entries."""
    if found.failure is not None:
        return (f"{name}: {found.failure.message}", _exit(returncode))
    if found.cut and not found.hits:
        return _late(name, deadline)
    if found.capped:
        return (
            f"{name} printed more than the plugin reads",
            "its hits above are the first it printed",
        )
    if found.cut:
        return (f"{name} stopped at {deadline} s", "its hits above are those it found by then")
    return (f"{name}: {found.skipped} entries could not be read", found.problem)


def summary(provider: Provider, report: Report | None, deadline: float) -> str:
    """A provider's last outcome, as the status keyword shows it."""
    if report is None:
        return "not searched since the plugin started"
    trouble = problem(provider, report, deadline)
    if trouble is not None:
        return f"last search: {trouble[0]}"
    count = len(_hits(report))
    return f"last search: {count} {'hit' if count == 1 else 'hits'}"


def rows(
    answers: Sequence[tuple[Provider, Report]], deadline: float, home: str
) -> tuple[Item, ...]:
    """The answer to a search: the merged hits, then a problem row per provider in trouble.

    When no provider found anything and none is in trouble, one row says so.
    """
    hits = [hit_row(merged, position, home) for position, merged in enumerate(interleave(answers))]
    problems = []
    for provider, report in answers:
        trouble = problem(provider, report, deadline)
        if trouble is not None:
            title, subtitle = trouble
            problems.append(
                Item(
                    id=f"problem:{provider.name}", title=title, subtitle=subtitle, icon=PROBLEM_ICON
                )
            )
    if hits or problems:
        return (*hits, *problems)
    names = ", ".join(provider.name for provider, _ in answers)
    scopes = "; ".join(
        f"{provider.name} searched {provider.scope}" for provider, _ in answers if provider.scope
    )
    return (
        Item(
            id="none",
            title=f"No hits in {names}",
            subtitle=scopes or None,
            icon=SymbolIcon("magnifyingglass"),
        ),
    )
