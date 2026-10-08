"""The pure half of the cache: when a value is too old."""


def expired(now: float, stamp: float | None, ttl: float) -> bool:
    """Whether a value stamped at ``stamp`` is due for a refresh at ``now``.

    No stamp means nothing was ever attempted. A clock that went backwards counts as expired.
    """
    return stamp is None or now < stamp or now - stamp >= ttl
