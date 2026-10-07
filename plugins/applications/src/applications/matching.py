"""How well a typed text matches an application's name, as a score in ``(0, 1]``.

Pure, and it imports nothing of ours. A match is a subsequence: every character of the
query appears in the name, in order. What makes one match better than another is where the
characters land. An exact name is 1.0. Otherwise three shares add up: how many characters
are anchored (at the start of a word, or straight after the previous match, so a prefix and
a set of initials such as "vsc" for Visual Studio Code are both fully anchored), how
tightly the matches sit together, and how much of the name the query covers, so a longer
query climbs towards, but never reaches, the exact score. The tests pin these orderings,
not the formula.
"""

INEXACT_CEILING = 0.95
"""The most an inexact match can score: strictly below an exact name."""

ANCHOR_WEIGHT = 0.45
"""The share for characters matched at a word start or straight after the previous match."""

TIGHTNESS_WEIGHT = 0.35
"""The share for how little of the name the matches span beyond their own length."""

COVERAGE_WEIGHT = 0.2
"""The share for how much of the name the query accounts for."""

WORD_BREAKS = frozenset(" -_.")
"""The characters after which a new word starts."""


def score(query: str, name: str) -> float | None:
    """The score of ``query`` against ``name``, or ``None`` when it does not match.

    Case is ignored. A blank query matches nothing: with nothing typed there is nothing
    to rank, and the launcher shows no rows.
    """
    wanted = query.strip().casefold()
    candidate = name.casefold()
    if not wanted:
        return None
    if wanted == candidate:
        return 1.0
    positions = _align(wanted, candidate)
    if positions is None:
        return None
    anchored = sum(
        1
        for previous, index in zip((None, *positions), positions, strict=False)
        if _starts_word(candidate, index) or (previous is not None and index == previous + 1)
    )
    span = positions[-1] - positions[0] + 1
    quality = (
        ANCHOR_WEIGHT * anchored / len(positions)
        + TIGHTNESS_WEIGHT * len(positions) / span
        + COVERAGE_WEIGHT * len(positions) / len(candidate)
    )
    return min(quality, 1.0) * INEXACT_CEILING


def _starts_word(name: str, index: int) -> bool:
    return index == 0 or name[index - 1] in WORD_BREAKS


def _align(query: str, name: str) -> tuple[int, ...] | None:
    """Where each query character lands in the name, anchored where it can be.

    Each character continues the previous match when the next letter of the name is the
    one wanted, so a prefix stays a prefix; otherwise it takes the next word start, so "sc"
    against "Visual Studio Code" lands on the S of Studio and the C of Code rather than the
    s inside Visual; failing both, the first plain occurrence.
    """
    positions: list[int] = []
    start = 0
    for character in query:
        if start < len(name) and name[start] == character:
            index = start
        else:
            index = next(
                (
                    candidate
                    for candidate in range(start, len(name))
                    if name[candidate] == character and _starts_word(name, candidate)
                ),
                name.find(character, start),
            )
        if index < 0:
            return None
        positions.append(index)
        start = index + 1
    return tuple(positions)
