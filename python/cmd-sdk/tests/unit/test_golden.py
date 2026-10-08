"""The SDK's side of the golden exchanges in docs/plugin-protocol.golden.json.

crates/cmd-core/tests/golden.rs checks the host against the same file. Here the SDK reads
every request as written, and writes every answer it would send exactly as written: for a
query, the items the host reads are the items this SDK writes.
"""

import json
import operator
from pathlib import Path
from typing import Any

import pytest
from cmd_sdk import Action, Close, Copy, Description, Effect, Icon, Item, Open, Plugin, Show
from cmd_sdk.protocol import (
    Describe,
    Failure,
    InvalidAnswerError,
    PathIcon,
    Query,
    Request,
    Run,
    SymbolIcon,
    agree,
    decode_request,
    dispatch,
    encode_response,
)

GOLDEN = Path(__file__).parents[4] / "docs" / "plugin-protocol.golden.json"
EXCHANGES: list[dict[str, Any]] = json.loads(GOLDEN.read_text(encoding="utf-8"))["exchanges"]
DESCRIPTION = Description("golden", "1.0.0", keyword="gold")


def icon_from(wire: dict[str, Any]) -> Icon:
    match wire["kind"]:
        case "path":
            return PathIcon(wire["path"])
        case "symbol":
            return SymbolIcon(wire["name"])
        case other:
            msg = f"this SDK has no icon kind {other!r}"
            raise ValueError(msg)


def item_from(wire: dict[str, Any]) -> Item:
    icon = wire.get("icon")
    return Item(
        id=wire["id"],
        title=wire["title"],
        subtitle=wire.get("subtitle"),
        score=wire.get("score"),
        actions=tuple(Action(action["id"], action["title"]) for action in wire.get("actions", [])),
        icon=None if icon is None else icon_from(icon),
    )


def effect_from(wire: dict[str, Any]) -> Effect:
    match wire["kind"]:
        case "close":
            return Close()
        case "copy":
            return Copy(wire["text"])
        case "open":
            return Open(wire["target"])
        case "show":
            return Show(wire["text"])
        case other:
            msg = f"this SDK has no effect kind {other!r}"
            raise ValueError(msg)


def expected_request(wire: dict[str, Any]) -> Request:
    params = wire["params"]
    match wire["method"]:
        case "describe":
            return Describe(
                wire["id"], params["protocol"], frozenset(params.get("capabilities", []))
            )
        case "query":
            return Query(wire["id"], params["text"])
        case "run":
            return Run(wire["id"], params["item"], params["action"])
        case other:
            msg = f"no method {other!r}"
            raise ValueError(msg)


def answer_of(plugin: Plugin, request: Request) -> dict[str, Any]:
    """What the SDK writes for this request, at the version a version 1 host agrees."""
    agreement = agree(Describe(0, 1))
    answer: dict[str, Any] = json.loads(encode_response(dispatch(request, plugin, agreement)))
    return answer


def answering(items: list[Item]) -> Plugin:
    return Plugin(DESCRIPTION, lambda _t: items, lambda _i, _a: Close())


def sent(wire: dict[str, Any], request: Request) -> list[dict[str, Any]]:
    """The items the SDK writes for a plugin that answers this item, read from the wire."""
    items: list[dict[str, Any]] = answer_of(answering([item_from(wire)]), request)["result"][
        "items"
    ]
    return items


def named(kind: str) -> list[dict[str, Any]]:
    return [
        exchange
        for exchange in EXCHANGES
        if exchange["request"]["method"] == kind and "error" not in exchange["answer"]
    ]


BY_NAME = operator.itemgetter("name")


@pytest.mark.parametrize("exchange", EXCHANGES, ids=BY_NAME)
def test_every_request_reads_as_written(exchange: dict[str, Any]) -> None:
    wire = exchange["request"]
    assert decode_request(json.dumps(wire)) == expected_request(wire)


@pytest.mark.parametrize("exchange", named("describe"), ids=BY_NAME)
def test_the_sdk_answers_describe_at_the_version_the_fixture_agrees(
    exchange: dict[str, Any],
) -> None:
    request = decode_request(json.dumps(exchange["request"]))
    answer = json.loads(encode_response(dispatch(request, answering([]))))
    assert answer == exchange["answer"]
    assert answer["result"] == exchange["host_reads"]["description"]


@pytest.mark.parametrize("exchange", named("query"), ids=BY_NAME)
def test_the_items_the_host_reads_are_the_items_the_sdk_writes(exchange: dict[str, Any]) -> None:
    reads = exchange["host_reads"]["items"]
    request = decode_request(json.dumps(exchange["request"]))
    assert answer_of(answering([item_from(item) for item in reads]), request) == {
        "id": exchange["request"]["id"],
        "result": {"items": reads},
    }


@pytest.mark.parametrize("exchange", named("query"), ids=BY_NAME)
def test_the_sdk_writes_each_answered_item_as_written_or_never_sends_it(
    exchange: dict[str, Any],
) -> None:
    never = set(exchange.get("sdk_never_sends", []))
    request = decode_request(json.dumps(exchange["request"]))
    for wire in exchange["answer"]["result"]["items"]:
        if wire["id"] in never:
            # Either the SDK has no way to say it, or it refuses to write it.
            with pytest.raises((KeyError, ValueError, InvalidAnswerError)):
                sent(wire, request)
        else:
            assert sent(wire, request) == [wire]


@pytest.mark.parametrize("exchange", named("run"), ids=BY_NAME)
def test_the_sdk_writes_the_effect_the_host_reads(exchange: dict[str, Any]) -> None:
    effect = effect_from(exchange["host_reads"]["effect"])
    plugin = Plugin(DESCRIPTION, lambda _t: (), lambda _i, _a: effect)
    request = decode_request(json.dumps(exchange["request"]))
    assert answer_of(plugin, request) == exchange["answer"]


@pytest.mark.parametrize(
    "exchange", [exchange for exchange in EXCHANGES if "error" in exchange["answer"]], ids=BY_NAME
)
def test_an_error_is_written_as_the_host_reads_it(exchange: dict[str, Any]) -> None:
    error = exchange["host_reads"]["error"]
    line = encode_response(Failure(exchange["request"]["id"], error["code"], error["message"]))
    assert json.loads(line) == exchange["answer"]
