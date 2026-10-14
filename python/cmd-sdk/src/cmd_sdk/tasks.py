"""Background tasks a plugin reports to the host (decision 12), as data.

A plugin that works between calls, such as an outbox retrying or an index being built,
reports a ``Task``. The host shows the latest state of each task by its ``id``. The line
goes to the host only when it named the ``tasks`` capability in ``describe``.

Everything here takes data and returns data, with the clock passed in. Writing the line,
and the lock it is written under, is ``reporter``'s job.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

CAPABILITY = "tasks"
"""The name the host puts in ``capabilities`` when it reads task lines."""

MIN_RUNNING_INTERVAL = 0.5
"""Seconds between two ``running`` updates of one task that the SDK sends: twice a second."""

type TaskState = Literal["running", "done", "failed"]

STATES = ("running", "done", "failed")


@dataclass(frozen=True)
class Task:
    """Background work and how it stands.

    ``id`` names the task within the plugin, so a later report replaces an earlier one.
    ``label`` is short text for the person. ``done`` and ``total``, given together, are how
    far along it is, with ``done`` at most ``total``; leave both out when there is no
    progress to show. ``detail`` is one line about what it is doing now.

    The host cuts text at 160 characters and drops control characters.
    """

    id: str
    label: str
    state: TaskState = "running"
    done: int | None = None
    total: int | None = None
    detail: str | None = None


class InvalidTaskError(ValueError):
    """A ``Task`` the protocol cannot carry. ``report`` raises it to the caller."""


def _text(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise InvalidTaskError(f"task {what} must be a str, not {type(value).__name__}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidTaskError(f"task {what} is not valid Unicode text") from None
    return value


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidTaskError(f"task {what} must be an int, not {type(value).__name__}")
    if value < 0:
        raise InvalidTaskError(f"task {what} is {value}, and must be 0 or more")
    return value


def task_json(task: object) -> dict[str, Any]:
    """The params of the ``task`` event for this task, checked.

    Raises:
        InvalidTaskError: It is not a ``Task``, a text field is not text, ``label`` or ``id``
            is empty, ``state`` is not one of ``running``, ``done`` and ``failed``, ``done``
            or ``total`` is not a whole number of 0 or more, only one of them is given, or
            ``done`` is above ``total``.
    """
    if not isinstance(task, Task):
        raise InvalidTaskError(f"report takes a Task, not a {type(task).__name__}")
    body: dict[str, Any] = {"id": _text(task.id, "id"), "label": _text(task.label, "label")}
    if not body["id"].strip():
        raise InvalidTaskError("task id must not be empty")
    if not body["label"].strip():
        raise InvalidTaskError("task label must not be empty")
    if task.state not in STATES:
        raise InvalidTaskError(f"task state must be one of {', '.join(STATES)}, not {task.state!r}")
    body["state"] = task.state
    if (task.done is None) != (task.total is None):
        raise InvalidTaskError("task done and total go together: give both or neither")
    if task.done is not None and task.total is not None:
        done, total = _count(task.done, "done"), _count(task.total, "total")
        if done > total:
            raise InvalidTaskError(f"task done ({done}) is more than total ({total})")
        body["done"], body["total"] = done, total
    if task.detail is not None:
        body["detail"] = _text(task.detail, "detail")
    return body


def encode_event(task: object) -> str:
    """The line to write for this task, newline included.

    A task ``task_json`` refuses raises its ``InvalidTaskError`` here.
    """
    body = {"event": "task", "params": task_json(task)}
    return json.dumps(body, ensure_ascii=False, allow_nan=False) + "\n"


class Throttle:
    """Decides which reports to send: a task is not sent more than twice a second.

    A ``running`` update is sent when the task's last sent report was not ``running``, or
    ``MIN_RUNNING_INTERVAL`` seconds have passed since it. A ``done`` or a ``failed`` is
    always sent. The latest ``running`` update withheld is dropped, not held back: the next
    report or the end of the task says where the task stands.

    Not thread-safe: the caller holds a lock around ``allow``.
    """

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._last_running: dict[str, float] = {}

    def allow(self, task: Task) -> bool:
        """Whether to send this (already checked) report, recording that it was."""
        if task.state != "running":
            self._last_running.pop(task.id, None)
            return True
        now = self._clock()
        last = self._last_running.get(task.id)
        if last is not None and now - last < MIN_RUNNING_INTERVAL:
            return False
        self._last_running[task.id] = now
        return True
