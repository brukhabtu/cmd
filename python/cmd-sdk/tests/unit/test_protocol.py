import json

import pytest
from cmd_sdk import Action, Close, Copy, Description, Item, Open, Plugin, Show
from cmd_sdk.protocol import (
    PROTOCOL,
    Describe,
    Failure,
    MalformedRequestError,
    Query,
    Run,
    Success,
    decode_request,
    dispatch,
    encode_response,
)

PLUGIN = Plugin(
    Description(name="echo", version="1.0", keyword="echo"),
    lambda text: (Item(id=text, title=text, score=0.5, actions=(Action("say", "Say it"),)),),
    lambda item, action: Copy(text=f"{item}/{action}"),
)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('{"id": 1, "method": "describe", "params": {"protocol": 0}}', Describe(1, 0)),
        ('{"id": 2, "method": "query", "params": {"text": "hi"}}', Query(2, "hi")),
        ('{"id": 3, "method": "run", "params": {"item": "a", "action": "b"}}', Run(3, "a", "b")),
    ],
)
def test_decodes_each_method(line: str, expected: Describe | Query | Run) -> None:
    assert decode_request(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "not json",
        "[]",
        '{"method": "query", "params": {"text": "x"}}',
        '{"id": "1", "method": "query", "params": {"text": "x"}}',
        '{"id": 1, "method": "query"}',
        '{"id": 1, "method": "query", "params": {"text": 5}}',
        '{"id": 1, "method": "describe", "params": {"protocol": true}}',
        '{"id": 1, "method": "dance", "params": {}}',
    ],
)
def test_rejects_malformed_requests(line: str) -> None:
    with pytest.raises(MalformedRequestError):
        decode_request(line)


def test_describe_adds_the_protocol_version() -> None:
    assert dispatch(Describe(1, 0), PLUGIN) == Success(
        1, {"name": "echo", "version": "1.0", "protocol": PROTOCOL, "keyword": "echo"}
    )


def test_query_serialises_items_with_only_the_fields_that_are_set() -> None:
    assert dispatch(Query(2, "hi"), PLUGIN) == Success(
        2,
        {
            "items": [
                {
                    "id": "hi",
                    "title": "hi",
                    "score": 0.5,
                    "actions": [{"id": "say", "title": "Say it"}],
                }
            ]
        },
    )
    bare = Plugin(Description("b", "0"), lambda _: (Item("x", "X"),), lambda _i, _a: Close())
    assert dispatch(Query(3, "x"), bare).result == {"items": [{"id": "x", "title": "X"}]}


@pytest.mark.parametrize(
    ("effect", "wire"),
    [
        (Close(), {"kind": "close"}),
        (Copy("t"), {"kind": "copy", "text": "t"}),
        (Open("https://a"), {"kind": "open", "target": "https://a"}),
        (Show("m"), {"kind": "show", "text": "m"}),
    ],
)
def test_run_tags_effects_by_kind(effect: Close | Copy | Open | Show, wire: dict[str, str]) -> None:
    plugin = Plugin(Description("e", "0"), lambda _: (), lambda _i, _a: effect)
    assert dispatch(Run(4, "i", "a"), plugin) == Success(4, {"effect": wire})


def test_responses_are_one_json_line() -> None:
    assert encode_response(Success(7, {"items": []})) == '{"id": 7, "result": {"items": []}}\n'
    line = encode_response(Failure(8, "bad_request", "why"))
    assert line.endswith("\n")
    assert json.loads(line) == {"id": 8, "error": {"code": "bad_request", "message": "why"}}
