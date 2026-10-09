"""Checks on single config values that more than one part of the schema makes.

Pure: each takes a value read from TOML and returns it checked, or raises ``InvalidError``
with the key and the rule in its message.
"""

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from search.hits import InvalidError

_NAME = re.compile(r"[A-Za-z0-9._-]+")


def is_word(value: object) -> bool:
    """Whether ``value`` is one word: text, not empty, no whitespace in or around it."""
    return (
        isinstance(value, str)
        and bool(value)
        and len(value.split()) == 1
        and value == value.strip()
    )


def program(value: object, key: str) -> str:
    """An absolute path to a program, without ``=`` (``env`` would take it for a variable).

    Raises:
        InvalidError: it is not.
    """
    if not isinstance(value, str) or not value:
        raise InvalidError(f"{key}: must be set, to an absolute path")
    if not PurePosixPath(value).is_absolute():
        raise InvalidError(f"{key}: {value!r} is not an absolute path")
    if "=" in value:
        raise InvalidError(f"{key}: {value!r} holds '=', which env would take for a variable")
    return value


def texts(table: Mapping[str, Any], key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    """A list of text, or ``default`` when the key is missing.

    Raises:
        InvalidError: it is not a list of text.
    """
    value = table.get(key)
    if value is None:
        return default
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise InvalidError(f"{key}: must be a list of text")
    return tuple(value)


def name(value: object, key: str, longest: int | None = None) -> str:
    """Letters, digits, ``.``, ``_`` and ``-``, and at most ``longest`` of them.

    Raises:
        InvalidError: it is not.
    """
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise InvalidError(f"{key}: must be letters, digits, '.', '_' or '-'")
    if longest is not None and len(value) > longest:
        raise InvalidError(f"{key}: must be at most {longest} characters")
    return value


def choice(value: object, key: str, allowed: tuple[str, ...]) -> str:
    """One of ``allowed``.

    Raises:
        InvalidError: it is not.
    """
    if isinstance(value, str) and value in allowed:
        return value
    names = " or ".join(f'"{option}"' for option in allowed)
    shown = "must be set" if value is None else f"{value!r} is not known"
    raise InvalidError(f"{key}: {shown}; it is {names}")
