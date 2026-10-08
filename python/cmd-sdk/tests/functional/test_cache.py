import threading

from cmd_sdk import TtlCache


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_the_first_get_returns_nothing_and_fills_in_the_background() -> None:
    clock = Clock()
    cache = TtlCache(lambda: "v1", 10, clock=clock)
    assert cache.get() is None
    cache.wait()
    assert cache.get() == "v1"


def test_block_first_waits_for_the_first_value() -> None:
    cache = TtlCache(lambda: "v1", 10, block_first=True, clock=Clock())
    assert cache.get() == "v1"


def test_a_fresh_value_is_served_without_producing() -> None:
    clock, calls = Clock(), []

    def produce() -> int:
        calls.append(1)
        return len(calls)

    cache = TtlCache(produce, 10, block_first=True, clock=clock)
    assert cache.get() == 1
    clock.now += 9
    assert cache.get() == 1
    assert len(calls) == 1


def test_a_stale_value_is_served_while_a_refresh_replaces_it() -> None:
    clock, calls = Clock(), []

    def produce() -> int:
        calls.append(1)
        return len(calls)

    cache = TtlCache(produce, 10, block_first=True, clock=clock)
    assert cache.get() == 1
    clock.now += 10
    assert cache.get() == 1  # the old value, at once
    cache.wait()
    assert cache.get() == 2


def test_two_refreshes_never_run_at_once() -> None:
    clock = Clock()
    started, release = threading.Event(), threading.Event()
    running, peak, calls = [0], [0], [0]

    def slow() -> int:
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        calls[0] += 1
        started.set()
        release.wait(5)
        running[0] -= 1
        return calls[0]

    cache = TtlCache(slow, 10, clock=clock)
    cache.get()
    assert started.wait(5)
    for _ in range(5):
        assert cache.get() is None  # the refresh is in flight; nobody starts another
    release.set()
    cache.wait()
    assert (calls[0], peak[0]) == (1, 1)
    assert cache.get() == 1


def test_a_failed_refresh_keeps_the_old_value_and_records_the_error() -> None:
    clock = Clock()
    outcomes: list[object] = ["v1", ValueError("down"), "v3"]

    def produce() -> str:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return str(outcome)

    cache = TtlCache(produce, 10, block_first=True, clock=clock)
    assert cache.get() == "v1"
    assert cache.error is None
    clock.now += 10
    cache.get()
    cache.wait()
    assert cache.get() == "v1"
    assert isinstance(cache.error, ValueError)
    clock.now += 10  # a failure waits another ttl before the next try
    cache.get()
    cache.wait()
    assert cache.get() == "v3"
    assert cache.error is None


def test_a_failed_first_fill_gives_nothing_and_is_not_retried_before_the_ttl() -> None:
    clock, calls = Clock(), []

    def produce() -> str:
        calls.append(1)
        raise OSError("no")

    cache = TtlCache(produce, 10, block_first=True, clock=clock)
    assert cache.get() is None
    assert isinstance(cache.error, OSError)
    clock.now += 5
    assert cache.get() is None
    cache.wait()
    assert len(calls) == 1
