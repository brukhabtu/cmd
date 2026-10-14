"""A reported task as data: what is checked, the line it becomes, and the throttle."""

import json
from typing import Any

import pytest
from cmd_sdk import InvalidTaskError, Task
from cmd_sdk.tasks import MIN_RUNNING_INTERVAL, Throttle, encode_event, task_json


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_a_task_becomes_the_event_line_of_the_protocol() -> None:
    task = Task("index", "Indexing notes", "running", 120, 900, "meetings/2026")
    line = encode_event(task)
    assert line.endswith("\n")
    assert json.loads(line) == {
        "event": "task",
        "params": {
            "id": "index",
            "label": "Indexing notes",
            "state": "running",
            "done": 120,
            "total": 900,
            "detail": "meetings/2026",
        },
    }
    assert "id" not in json.loads(line), "an event has no id, or the host reads a response"


def test_a_task_with_no_progress_and_no_detail_leaves_them_out() -> None:
    assert task_json(Task("a", "A", "done")) == {"id": "a", "label": "A", "state": "done"}


def test_the_state_defaults_to_running() -> None:
    assert task_json(Task("a", "A"))["state"] == "running"


@pytest.mark.parametrize("state", ["running", "done", "failed"])
def test_every_state_is_carried(state: Any) -> None:
    assert task_json(Task("a", "A", state))["state"] == state


@pytest.mark.parametrize(
    ("task", "message"),
    [
        pytest.param("index", "takes a Task", id="not a task"),
        pytest.param(Task(3, "A"), "id must be a str", id="id not text"),  # type: ignore[arg-type]
        pytest.param(Task("", "A"), "id must not be empty", id="empty id"),
        pytest.param(Task("a", 4), "label must be a str", id="label not text"),  # type: ignore[arg-type]
        pytest.param(Task("a", " "), "label must not be empty", id="blank label"),
        pytest.param(Task("a", "A", "paused"), "state must be one of", id="unknown state"),  # type: ignore[arg-type]
        pytest.param(Task("a", "A", done=1), "go together", id="done without total"),
        pytest.param(Task("a", "A", total=1), "go together", id="total without done"),
        pytest.param(Task("a", "A", done=2, total=1), "more than total", id="done above total"),
        pytest.param(Task("a", "A", done=-1, total=1), "0 or more", id="negative done"),
        pytest.param(Task("a", "A", done=1.5, total=2), "done must be an int", id="float done"),  # type: ignore[arg-type]
        pytest.param(Task("a", "A", done=True, total=2), "done must be an int", id="bool done"),
        pytest.param(Task("a", "A", detail=7), "detail must be a str", id="detail not text"),  # type: ignore[arg-type]
        pytest.param(Task("a", "\ud800"), "not valid Unicode", id="lone surrogate"),
    ],
)
def test_a_task_the_protocol_cannot_carry_raises_to_the_caller(task: object, message: str) -> None:
    with pytest.raises(InvalidTaskError, match=message):
        encode_event(task)


def test_an_invalid_task_error_is_a_value_error() -> None:
    assert issubclass(InvalidTaskError, ValueError)


def running(task_id: str = "a") -> Task:
    return Task(task_id, "A", "running", 1, 9)


def test_a_running_update_is_sent_at_most_twice_a_second() -> None:
    clock = Clock()
    throttle = Throttle(clock)
    assert throttle.allow(running()), "the first is sent"
    clock.advance(MIN_RUNNING_INTERVAL - 0.01)
    assert not throttle.allow(running()), "another within half a second is not"
    clock.advance(0.01)
    assert throttle.allow(running()), "at half a second it is"
    clock.advance(0.1)
    assert not throttle.allow(running())


def test_a_withheld_update_does_not_move_the_window() -> None:
    clock = Clock()
    throttle = Throttle(clock)
    assert throttle.allow(running())
    clock.advance(0.3)
    assert not throttle.allow(running())
    clock.advance(0.3)
    # 0.6 s after the one that was sent, but only 0.3 s after the one withheld: the
    # allowance is measured from what was sent.
    assert throttle.allow(running())


def test_throttling_is_per_task() -> None:
    clock = Clock()
    throttle = Throttle(clock)
    assert throttle.allow(running("a"))
    assert throttle.allow(running("b")), "another task has its own allowance"
    assert not throttle.allow(running("a"))


@pytest.mark.parametrize("state", ["done", "failed"])
def test_a_change_of_state_is_always_sent(state: Any) -> None:
    clock = Clock()
    throttle = Throttle(clock)
    assert throttle.allow(running())
    assert throttle.allow(Task("a", "A", state)), "immediately after a running update"
    assert throttle.allow(Task("a", "A", state)), "and again: a final state is never withheld"


def test_a_task_that_ended_and_runs_again_is_sent_at_once() -> None:
    clock = Clock()
    throttle = Throttle(clock)
    assert throttle.allow(running())
    assert throttle.allow(Task("a", "A", "failed"))
    assert throttle.allow(running()), "running again is a change of state"
