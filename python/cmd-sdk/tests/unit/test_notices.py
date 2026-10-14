"""A notice as data: what is checked and the line it becomes."""

import json
from typing import Any

import pytest
from cmd_sdk import InvalidNoticeError
from cmd_sdk.notices import encode_event, notice_json


def test_a_notice_becomes_the_event_line_of_the_protocol() -> None:
    line = encode_event("PROJ-12", "PROJ-12 moved", "In Review", "https://example.test/PROJ-12")
    assert line.endswith("\n")
    assert json.loads(line) == {
        "event": "notify",
        "params": {
            "id": "PROJ-12",
            "title": "PROJ-12 moved",
            "body": "In Review",
            "open": "https://example.test/PROJ-12",
        },
    }
    assert "id" not in json.loads(line), "an event has no id, or the host reads a response"


def test_body_and_open_are_left_out_when_not_given() -> None:
    assert notice_json("a", "A") == {"id": "a", "title": "A"}


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((3, "T"), "id must be a str, not int"),
        (("a", None), "title must be a str, not NoneType"),
        (("", "T"), "id must not be empty"),
        (("a", "  "), "title must not be empty"),
        (("a", "T", 4), "body must be a str"),
        (("a", "T", None, 4), "open must be a str"),
        (("a", "T", None, " "), "open must not be empty"),
        (("a", "\ud800"), "title is not valid Unicode text"),
    ],
)
def test_a_notice_the_protocol_cannot_carry_raises(args: tuple[Any, ...], message: str) -> None:
    with pytest.raises(InvalidNoticeError, match=message):
        encode_event(*args)


def test_an_empty_body_is_allowed_and_left_to_the_host() -> None:
    assert notice_json("a", "A", "") == {"id": "a", "title": "A", "body": ""}
