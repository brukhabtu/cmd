import io
import json
from collections.abc import Sequence
from typing import Any

from cmd_sdk import Close, Item, Show, serve
from system import PLUGIN, plugin
from system.commands import DARK_MODE, SLEEP


class Recorder:
    """An executor that runs nothing: it records each argv and answers one fixed failure."""

    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> str | None:
        self.calls.append(tuple(argv))
        return self.failure


def test_a_command_is_one_definite_item_with_no_score_and_no_actions() -> None:
    (item,) = PLUGIN.query("lo")
    assert item == Item(id="lock", title="Lock screen", subtitle="Locks the screen")
    assert item.score is None
    assert item.actions == ()


def test_other_text_yields_nothing() -> None:
    assert PLUGIN.query("safari") == ()


def test_enter_performs_the_command_and_closes() -> None:
    executor = Recorder()
    assert plugin(execute=executor, platform="darwin").run("sleep", "default") == Close()
    assert executor.calls == [SLEEP.argv]


def test_a_failure_is_shown_with_the_command_named() -> None:
    executor = Recorder("No such file")
    effect = plugin(execute=executor, platform="darwin").run("dark-mode", "default")
    assert effect == Show(text="Toggle dark mode: No such file")
    assert executor.calls == [DARK_MODE.argv]


def test_off_a_mac_nothing_runs_and_the_reason_is_shown() -> None:
    executor = Recorder()
    effect = plugin(execute=executor, platform="linux").run("sleep", "default")
    assert isinstance(effect, Show)
    assert "macOS" in effect.text
    assert executor.calls == []


def test_an_unknown_item_or_action_is_shown_not_run() -> None:
    executor = Recorder()
    system = plugin(execute=executor, platform="darwin")
    assert isinstance(system.run("nothing", "default"), Show)
    assert isinstance(system.run("sleep", "dance"), Show)
    assert executor.calls == []


def _serve(*lines: str) -> list[dict[str, Any]]:
    sink = io.StringIO()
    serve(PLUGIN, io.StringIO("".join(line + "\n" for line in lines)), sink)
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def test_on_the_wire_the_plugin_has_no_keyword_and_its_items_carry_no_score() -> None:
    answers = _serve(
        '{"id": 1, "method": "describe", "params": {"protocol": 0}}',
        '{"id": 2, "method": "query", "params": {"text": "sle"}}',
    )
    assert answers[0]["result"] == {"name": "system", "version": "0.1.0", "protocol": 0}
    assert answers[1]["result"] == {
        "items": [{"id": "sleep", "title": "Sleep", "subtitle": "Puts the Mac to sleep"}]
    }
