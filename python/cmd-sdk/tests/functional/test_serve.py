"""The world is stdin and stdout; here they are StringIO, and we assert on what was written."""

import io
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest
from cmd_sdk import Action, Copy, Description, Effect, Item, PathIcon, Plugin, serve


def _explode(_text: str) -> tuple[Item, ...]:
    msg = "the calculator caught fire"
    raise RuntimeError(msg)


def _not_json(constant: str) -> NoReturn:
    # json.loads takes NaN and Infinity, which the host's parser does not: read as it would.
    msg = f"{constant} is not JSON"
    raise ValueError(msg)


def run(plugin: Plugin, *lines: str) -> list[dict[str, Any]]:
    sink = io.StringIO()
    serve(plugin, io.StringIO("".join(line + "\n" for line in lines)), sink)
    return [json.loads(line, parse_constant=_not_json) for line in sink.getvalue().splitlines()]


def query(request_id: int, text: str) -> str:
    return json.dumps({"id": request_id, "method": "query", "params": {"text": text}})


def answering(item: Item) -> Plugin:
    """A plugin whose answer to "bad" is this item, and to anything else a good one."""

    def answer(text: str) -> tuple[Item, ...]:
        return (item,) if text == "bad" else (Item(text, text),)

    return Plugin(Description("p", "1"), answer, lambda i, _a: Copy(i))


def running(effect: Effect) -> Plugin:
    """A plugin whose run of the item "bad" gives this effect, and of any other a copy."""

    def act(item: str, _action: str) -> Effect:
        return effect if item == "bad" else Copy(item)

    return Plugin(Description("p", "1"), lambda t: (Item(t, t),), act)


def run_of(request_id: int, item: str) -> str:
    return json.dumps({
        "id": request_id,
        "method": "run",
        "params": {"item": item, "action": "default"},
    })


def test_answers_each_request_in_order_and_stops_at_end_of_input() -> None:
    plugin = Plugin(
        Description("up", "1"), lambda t: (Item(t.upper(), t.upper()),), lambda i, _a: Copy(i)
    )
    answers = run(
        plugin,
        '{"id": 1, "method": "describe", "params": {"protocol": 1}}',
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


def test_a_print_in_a_plugin_goes_to_stderr_and_stdout_keeps_only_the_protocol(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def chatty(text: str) -> tuple[Item, ...]:
        print("debugging", text)  # ruff: ignore[print] - the stray print is the point
        return (Item(text, text),)

    monkeypatch.setattr(sys, "stdin", io.StringIO(query(1, "a") + "\n" + query(2, "b") + "\n"))
    stdout_before = sys.stdout

    serve(Plugin(Description("chatty", "1"), chatty, lambda i, _a: Copy(i)))

    out, err = capsys.readouterr()
    assert [json.loads(line)["id"] for line in out.splitlines()] == [1, 2]
    assert err.splitlines() == ["debugging a", "debugging b"]
    assert sys.stdout is stdout_before


def test_an_unknown_method_is_answered_with_its_own_id_and_the_loop_goes_on() -> None:
    answers = run(
        answering(Item("a", "A")),
        '{"id": 7, "method": "dance", "params": {}}',
        '{"id": 8, "method": "dance"}',
        query(9, "x"),
    )
    assert [a["id"] for a in answers] == [7, 8, 9]
    assert [a["error"]["code"] for a in answers[:2]] == ["unknown_method", "unknown_method"]
    assert answers[0]["error"]["message"] == "unknown method 'dance'"
    assert "result" in answers[2]


def test_a_bad_request_with_an_id_is_answered_with_that_id() -> None:
    answers = run(
        answering(Item("a", "A")),
        '{"id": 5, "method": "query", "params": {"text": 3}}',
        '{"id": 6, "method": "query"}',
        '{"method": "query", "params": {"text": "x"}}',
    )
    assert [a["id"] for a in answers] == [5, 6, 0]
    assert {a["error"]["code"] for a in answers} == {"bad_request"}


@pytest.mark.parametrize(
    ("wrong", "said"),
    [
        pytest.param(
            Item("a.app", "A", icon=PathIcon(Path("/Applications/A.app"))),  # type: ignore[arg-type]
            "item 1 ('a.app'): icon path must be a str, not PosixPath",
            id="a Path inside a PathIcon",
        ),
        pytest.param(
            Item("a", "A", icon=Path("/Applications/A.app")),  # type: ignore[arg-type]
            "item 1 ('a'): icon must be a PathIcon or a SymbolIcon, not PosixPath",
            id="a Path as the icon",
        ),
        pytest.param(
            Item("a", "A", score=float("nan")), "item 1 ('a'): score is nan", id="a NaN score"
        ),
        pytest.param(
            Item("a", "A", score=float("inf")), "item 1 ('a'): score is inf", id="an infinite score"
        ),
        pytest.param(
            Item("a", "A", score=-float("inf")),
            "item 1 ('a'): score is -inf",
            id="a negative infinite score",
        ),
        pytest.param(
            Item("a", "A", score=True),
            "item 1 ('a'): score must be a number, not bool",
            id="a bool score",
        ),
        pytest.param(
            Item("a", 5),  # type: ignore[arg-type]
            "item 1 ('a'): title must be a str, not int",
            id="a title that is not text",
        ),
        pytest.param(
            Item(5, "five"),  # type: ignore[arg-type]
            "item 1: id must be a str, not int",
            id="an id that is not text",
        ),
        pytest.param(
            Item("a", "A", actions=(Action("copy", None),)),  # type: ignore[arg-type]
            "item 1 ('a'): action title must be a str, not NoneType",
            id="an action without a title",
        ),
        pytest.param(
            Item("a", "caf\udce9"),
            "UnicodeEncodeError",
            id="text that is not valid Unicode, as a file name in bytes that were not UTF-8",
        ),
    ],
)
def test_a_bad_item_is_a_plugin_error_that_names_it_and_the_loop_goes_on(
    wrong: Item, said: str
) -> None:
    answers = run(answering(wrong), query(1, "bad"), query(2, "good"))

    assert [a["id"] for a in answers] == [1, 2]
    assert answers[0]["error"]["code"] == "plugin_error"
    assert said in answers[0]["error"]["message"]
    assert answers[1]["result"] == {"items": [{"id": "good", "title": "good"}]}


def test_the_second_item_of_an_answer_is_named_by_its_place() -> None:
    plugin = Plugin(
        Description("p", "1"),
        lambda _t: (Item("fine", "Fine"), Item("odd", "Odd", score=float("nan"))),
        lambda i, _a: Copy(i),
    )
    answers = run(plugin, query(1, "x"))
    assert answers[0]["error"]["message"].startswith("InvalidAnswerError: item 2 ('odd'): score")


@pytest.mark.parametrize(
    ("effect", "said"),
    [
        pytest.param(None, "run must return a Close, Copy, Open or Show, not NoneType", id="none"),
        pytest.param(Copy(5), "copy text must be a str, not int", id="copy without text"),  # type: ignore[arg-type]
    ],
)
def test_a_bad_effect_is_a_plugin_error_and_the_loop_goes_on(
    effect: Effect | None, said: str
) -> None:
    answers = run(
        running(effect),  # type: ignore[arg-type]
        run_of(1, "bad"),
        run_of(2, "good"),
    )

    assert [a["id"] for a in answers] == [1, 2]
    assert answers[0]["error"]["code"] == "plugin_error"
    assert said in answers[0]["error"]["message"]
    assert answers[1]["result"] == {"effect": {"kind": "copy", "text": "good"}}


def test_an_exception_message_that_is_not_valid_unicode_is_escaped_not_fatal() -> None:
    def raises(_text: str) -> tuple[Item, ...]:
        msg = "no such file: caf\udce9"
        raise FileNotFoundError(msg)

    answers = run(
        Plugin(Description("p", "1"), raises, lambda i, _a: Copy(i)), query(1, "x"), query(2, "y")
    )

    assert [a["id"] for a in answers] == [1, 2]
    assert answers[0]["error"]["message"] == "FileNotFoundError: no such file: caf\\udce9"
