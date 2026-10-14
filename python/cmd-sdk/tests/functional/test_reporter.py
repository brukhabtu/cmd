"""``report`` on a real stream: gated by the agreement, throttled, under the one lock."""

import io
import json
import threading
import time
from typing import Any

import pytest
from cmd_sdk import Close, Description, InvalidTaskError, Item, Plugin, Task, report, serve
from cmd_sdk.protocol import Agreement
from cmd_sdk.reporter import Reporter, installed


class Clock:
    def __init__(self) -> None:
        self.now = 50.0

    def __call__(self) -> float:
        return self.now


def lines(sink: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def reporter_for(*capabilities: str) -> tuple[Reporter, io.StringIO, Clock]:
    sink = io.StringIO()
    clock = Clock()
    reporter = Reporter(sink, clock)
    reporter.agree(Agreement(1, frozenset(capabilities)))
    return reporter, sink, clock


def test_a_report_is_written_when_the_host_named_tasks() -> None:
    reporter, sink, _ = reporter_for("tasks")
    reporter.report(Task("index", "Indexing", "running", 1, 9))
    assert lines(sink) == [
        {
            "event": "task",
            "params": {
                "id": "index",
                "label": "Indexing",
                "state": "running",
                "done": 1,
                "total": 9,
            },
        }
    ]


@pytest.mark.parametrize("capabilities", [(), ("keywords",)], ids=["none", "others only"])
def test_a_report_is_silent_when_the_host_did_not_name_tasks(capabilities: tuple[str, ...]) -> None:
    reporter, sink, _ = reporter_for(*capabilities)
    reporter.report(Task("index", "Indexing", "failed"))
    assert not sink.getvalue()


def test_a_report_is_silent_before_any_describe() -> None:
    sink = io.StringIO()
    Reporter(sink).report(Task("index", "Indexing"))
    assert not sink.getvalue()


def test_a_silent_report_still_checks_the_task() -> None:
    reporter, sink, _ = reporter_for()
    with pytest.raises(InvalidTaskError, match="more than total"):
        reporter.report(Task("a", "A", done=3, total=2))
    assert not sink.getvalue()


def test_an_invalid_task_writes_nothing_when_the_host_reads_tasks() -> None:
    reporter, sink, _ = reporter_for("tasks")
    with pytest.raises(InvalidTaskError):
        reporter.report(Task("a", ""))
    assert not sink.getvalue()


def test_running_updates_are_throttled_with_the_clock_it_was_given() -> None:
    reporter, sink, clock = reporter_for("tasks")
    for done in range(1, 4):
        reporter.report(Task("a", "A", "running", done, 9))
    assert [line["params"]["done"] for line in lines(sink)] == [1]
    clock.now += 0.5
    reporter.report(Task("a", "A", "running", 4, 9))
    reporter.report(Task("a", "A", "done"))
    reporter.report(Task("a", "A", "failed"))
    assert [(line["params"]["state"], line["params"].get("done")) for line in lines(sink)] == [
        ("running", 1),
        ("running", 4),
        ("done", None),
        ("failed", None),
    ]


def test_a_withheld_report_is_not_counted_against_a_silent_host() -> None:
    """Throttle state is kept only for reports the host would read."""
    reporter, sink, _ = reporter_for()
    reporter.report(Task("a", "A"))
    reporter.agree(Agreement(1, frozenset({"tasks"})))
    reporter.report(Task("a", "A"))
    assert len(lines(sink)) == 1


def test_a_closed_stream_is_dropped_not_raised_into_the_plugin() -> None:
    reporter, sink, _ = reporter_for("tasks")
    sink.close()
    reporter.report(Task("a", "A", "done"))


class SlowSink(io.StringIO):
    """A stream that writes a line a character at a time and notices a second writer."""

    def __init__(self) -> None:
        super().__init__()
        self.writers = 0
        self.overlaps = 0

    def write(self, text: str, /) -> int:
        self.writers += 1
        if self.writers > 1:
            self.overlaps += 1
        try:
            for character in text:
                super().write(character)
                time.sleep(0.00005)
        finally:
            self.writers -= 1
        return len(text)


def test_answers_and_reports_from_two_threads_never_interleave() -> None:
    sink = SlowSink()
    reporter = Reporter(sink)
    reporter.agree(Agreement(1, frozenset({"tasks"})))
    answer = json.dumps({"id": 1, "result": {"items": [{"id": "a", "title": "x" * 40}]}}) + "\n"

    def answering() -> None:
        for _ in range(60):
            reporter.write(answer)

    def reporting() -> None:
        for number in range(60):
            # done and failed are never throttled, so each one is a line
            reporter.report(Task(f"t{number}", "A task with a label", "done"))

    threads = [threading.Thread(target=answering), threading.Thread(target=reporting)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sink.overlaps == 0, "two writes were in the stream at once"
    written = sink.getvalue().splitlines()
    assert len(written) == 120
    parsed = [json.loads(line) for line in written]
    assert sum("event" in line for line in parsed) == 60
    assert sum("id" in line for line in parsed) == 60


def request(request_id: int, method: str, params: dict[str, Any]) -> str:
    return json.dumps({"id": request_id, "method": method, "params": params}) + "\n"


def serve_lines(plugin: Plugin, *requests: str) -> list[dict[str, Any]]:
    sink = io.StringIO()
    serve(plugin, io.StringIO("".join(requests)), sink)
    return lines(sink)


def reporting_plugin() -> Plugin:
    def query(text: str) -> tuple[Item, ...]:
        report(Task("index", "Indexing notes", "running", 1, 3))
        report(Task("index", "Indexing notes", "running", 2, 3))
        worker = threading.Thread(target=report, args=(Task("index", "Indexing notes", "done"),))
        worker.start()
        worker.join()
        return (Item(text, text),)

    return Plugin(Description("reporter", "1"), query, lambda _i, _a: Close())


def test_serve_writes_a_plugin_s_reports_between_the_describe_and_its_answers() -> None:
    written = serve_lines(
        reporting_plugin(),
        request(1, "describe", {"protocol": 1, "capabilities": ["tasks"]}),
        request(2, "query", {"text": "go"}),
    )
    assert [line.get("event", line.get("id")) for line in written] == [1, "task", "task", 2]
    states = [line["params"]["state"] for line in written if "event" in line]
    assert states == ["running", "done"], "the second running update is inside the half second"
    assert written[-1]["result"] == {"items": [{"id": "go", "title": "go"}]}


@pytest.mark.parametrize(
    "params",
    [{"protocol": 1, "capabilities": []}, {"protocol": 1}, {"protocol": 0}],
    ids=["no tasks", "a host older than capabilities", "version 0"],
)
def test_serve_sends_a_host_that_did_not_name_tasks_only_answers(params: dict[str, Any]) -> None:
    written = serve_lines(
        reporting_plugin(),
        request(1, "describe", params),
        request(2, "query", {"text": "go"}),
    )
    assert [line["id"] for line in written] == [1, 2]
    assert all("event" not in line for line in written)


def test_a_report_before_any_describe_is_not_sent() -> None:
    written = serve_lines(reporting_plugin(), request(1, "query", {"text": "go"}))
    assert [line["id"] for line in written] == [1]


def test_a_plugin_that_reports_an_invalid_task_gets_a_plugin_error_and_serve_goes_on() -> None:
    def query(text: str) -> tuple[Item, ...]:
        if text == "bad":
            report(Task("a", "A", done=5, total=1))
        return (Item(text, text),)

    written = serve_lines(
        Plugin(Description("p", "1"), query, lambda _i, _a: Close()),
        request(1, "describe", {"protocol": 1, "capabilities": ["tasks"]}),
        request(2, "query", {"text": "bad"}),
        request(3, "query", {"text": "fine"}),
    )
    assert [line["id"] for line in written] == [1, 2, 3]
    assert written[1]["error"]["code"] == "plugin_error"
    assert "InvalidTaskError" in written[1]["error"]["message"]
    assert "result" in written[2]


def test_report_outside_serve_checks_the_task_and_writes_nothing() -> None:
    report(Task("a", "A"))
    with pytest.raises(InvalidTaskError):
        report(Task("a", "A", "paused"))  # type: ignore[arg-type]


def test_the_reporter_serve_installed_is_gone_when_serve_returns() -> None:
    sink = io.StringIO()
    describe = request(1, "describe", {"protocol": 1, "capabilities": ["tasks"]})
    serve(reporting_plugin(), io.StringIO(describe), sink)
    before = sink.getvalue()
    report(Task("late", "Late", "done"))
    assert sink.getvalue() == before, "a report after serve returned has nowhere to go"


def test_installed_restores_the_previous_reporter() -> None:
    outer, outer_sink, _ = reporter_for("tasks")
    inner, inner_sink, _ = reporter_for("tasks")
    with installed(outer):
        with installed(inner):
            report(Task("a", "A", "done"))
        report(Task("b", "B", "done"))
    assert len(lines(inner_sink)) == 1
    assert [line["params"]["id"] for line in lines(outer_sink)] == ["b"]
