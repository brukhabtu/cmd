import json

import pytest
from cmd_sdk import (
    Action,
    Close,
    Copy,
    Description,
    Icon,
    Item,
    Open,
    PathIcon,
    Plugin,
    Show,
    SymbolIcon,
)
from cmd_sdk.protocol import (
    PROTOCOL,
    Describe,
    Failure,
    InvalidAnswerError,
    MalformedRequestError,
    Query,
    Run,
    Success,
    UnknownMethodError,
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
        ('{"id": 1, "method": "describe", "params": {"protocol": 1}}', Describe(1, 1)),
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
    assert PROTOCOL == 1
    assert dispatch(Describe(1, 1), PLUGIN) == Success(
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
    ("icon", "wire"),
    [
        (
            PathIcon("/Applications/Safari.app"),
            {"kind": "path", "path": "/Applications/Safari.app"},
        ),
        (SymbolIcon("globe"), {"kind": "symbol", "name": "globe"}),
    ],
)
def test_icons_are_tagged_by_kind(icon: Icon, wire: dict[str, str]) -> None:
    plugin = Plugin(
        Description("i", "0"), lambda _: (Item("x", "X", icon=icon),), lambda _i, _a: Close()
    )
    assert dispatch(Query(5, "x"), plugin).result == {
        "items": [{"id": "x", "title": "X", "icon": wire}]
    }


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


def test_a_request_for_an_unknown_method_is_an_unknown_method_error_with_its_id() -> None:
    for line in (
        '{"id": 12, "method": "dance", "params": {}}',
        '{"id": 12, "method": "dance"}',
        '{"id": 12, "method": "dance", "params": 5}',
    ):
        with pytest.raises(UnknownMethodError, match="unknown method 'dance'") as caught:
            decode_request(line)
        assert caught.value.request_id == 12


@pytest.mark.parametrize(
    ("line", "request_id"),
    [
        ("not json", 0),
        ("[]", 0),
        ('{"method": "query", "params": {"text": "x"}}', 0),
        ('{"id": 4, "method": "query"}', 4),
        ('{"id": 4, "method": 5, "params": {}}', 4),
        ('{"id": 4, "method": "query", "params": {"text": 5}}', 4),
        ('{"id": 4, "method": "run", "params": {"item": "a"}}', 4),
    ],
)
def test_a_malformed_request_carries_its_id_when_it_had_one(line: str, request_id: int) -> None:
    with pytest.raises(MalformedRequestError) as caught:
        decode_request(line)
    assert not isinstance(caught.value, UnknownMethodError)
    assert caught.value.request_id == request_id


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_a_response_json_has_no_form_for_is_refused_not_written_as_nan(number: float) -> None:
    with pytest.raises(ValueError, match="not JSON compliant"):
        encode_response(Success(1, {"score": number}))


def test_a_response_with_text_that_is_not_valid_unicode_is_refused() -> None:
    with pytest.raises(ValueError, match="surrogates not allowed"):
        encode_response(Success(1, {"title": "caf\udce9"}))


def test_non_ascii_text_stays_as_it_is_on_the_wire() -> None:
    assert encode_response(Success(1, {"title": "café ⌘"})) == (
        '{"id": 1, "result": {"title": "café ⌘"}}\n'
    )


def test_an_item_that_is_not_an_item_is_named_by_its_place() -> None:
    plugin = Plugin(Description("p", "1"), lambda _t: (Item("a", "A"), {"id": "b"}), PLUGIN.run)  # type: ignore[arg-type,return-value]
    with pytest.raises(InvalidAnswerError, match="item 2 is a dict"):
        dispatch(Query(1, "x"), plugin)


def test_a_finite_score_of_any_number_type_is_carried_as_it_is() -> None:
    plugin = Plugin(
        Description("p", "1"),
        lambda _t: (Item("a", "A", score=1), Item("b", "B", score=0.25), Item("c", "C", score=0)),
        PLUGIN.run,
    )
    result = dispatch(Query(1, "x"), plugin).result
    assert [item["score"] for item in result["items"]] == [1, 0.25, 0]
