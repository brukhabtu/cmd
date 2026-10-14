"""A notice a plugin sends the person (decision 13), as data.

A plugin that watches something, such as a ticket changing status, sends a notice when it
sees the change. The host posts it and keeps it in a recent list; a later notice with the
same ``id`` replaces the earlier one there. The line goes to the host only when it named the
``notify`` capability in ``describe``.

Everything here takes data and returns data. Writing the line, and the lock it is written
under, is ``reporter``'s job.
"""

import json
from typing import Any

CAPABILITY = "notify"
"""The name the host puts in ``capabilities`` when it reads notify lines."""


class InvalidNoticeError(ValueError):
    """A notice the protocol cannot carry. ``notify`` raises it to the caller."""


def _text(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise InvalidNoticeError(f"notice {what} must be a str, not {type(value).__name__}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InvalidNoticeError(f"notice {what} is not valid Unicode text") from None
    return value


def notice_json(
    id: object,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
    title: object,
    body: object = None,
    open: object = None,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
) -> dict[str, Any]:
    """The params of the ``notify`` event for this notice, checked.

    Raises:
        InvalidNoticeError: ``id`` or ``title`` is not text or is empty, or ``body`` or ``open``
            is given and is not text, or ``open`` is empty.
    """
    params: dict[str, Any] = {"id": _text(id, "id"), "title": _text(title, "title")}
    if not params["id"].strip():
        raise InvalidNoticeError("notice id must not be empty")
    if not params["title"].strip():
        raise InvalidNoticeError("notice title must not be empty")
    if body is not None:
        params["body"] = _text(body, "body")
    if open is not None:
        params["open"] = _text(open, "open")
        if not params["open"].strip():
            raise InvalidNoticeError("notice open must not be empty")
    return params


def encode_event(
    id: object,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
    title: object,
    body: object = None,
    open: object = None,  # ruff: ignore[builtin-argument-shadowing] - the protocol's own name for the field
) -> str:
    """The line to write for this notice, newline included.

    A notice ``notice_json`` refuses raises its ``InvalidNoticeError`` here.
    """
    line = {"event": "notify", "params": notice_json(id, title, body, open)}
    return json.dumps(line, ensure_ascii=False, allow_nan=False) + "\n"
