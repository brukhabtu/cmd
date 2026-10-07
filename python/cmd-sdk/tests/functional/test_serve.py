"""The world is stdin and stdout; here they are StringIO, and we assert on what was written."""

import io
import json
from typing import Any

from cmd_sdk import Copy, Description, Item, Plugin, serve


def _explode(_text: str) -> tuple[Item, ...]:
    msg = "the calculator caught fire"
    raise RuntimeError(msg)


def run(plugin: Plugin, *lines: str) -> list[dict[str, Any]]:
    sink = io.StringIO()
    serve(plugin, io.StringIO("".join(line + "\n" for line in lines)), sink)
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def test_answers_each_request_in_order_and_stops_at_end_of_input() -> None:
    plugin = Plugin(
        Description("up", "1"), lambda t: (Item(t.upper(), t.upper()),), lambda i, _a: Copy(i)
    )
    answers = run(
        plugin,
        '{"id": 1, "method": "describe", "params": {"protocol": 0}}',
        "",
        '{"id": 2, "method": "query", "params": {"text": "hi"}}',
        '{"id": 3, "method": "run", "params": {"item": "HI", "action": "default"}}',
    )
    assert [a["id"] for a in answers] == [1, 2, 3]
    assert answers[1]["result"] == {"items": [{"id": "HI", "title": "HI"}]}
    assert answers[2]["result"] == {"effect": {"kind": "copy", "text": "HI"}}


def test_a_bad_line_gets_an_error_and_the_loop_goes_on() -> None:
    plugin = Plugin(Description("up", "1"), lambda t: (Item(t, t),), lambda i, _a: Copy(i))
    answers = run(plugin, "garbage", '{"id": 9, "method": "query", "params": {"text": "x"}}')
    assert answers[0]["id"] == 0
    assert answers[0]["error"]["code"] == "bad_request"
    assert answers[1]["id"] == 9


def test_a_plugin_exception_becomes_a_plugin_error_response() -> None:
    plugin = Plugin(Description("boom", "1"), _explode, lambda i, _a: Copy(i))
    answers = run(plugin, '{"id": 4, "method": "query", "params": {"text": "x"}}')
    assert answers == [
        {
            "id": 4,
            "error": {
                "code": "plugin_error",
                "message": "RuntimeError: the calculator caught fire",
            },
        }
    ]
