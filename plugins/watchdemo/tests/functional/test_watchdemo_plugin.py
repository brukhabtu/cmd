"""The plugin against a tickets file the tests edit, with the host's directories and clocks faked.

The polling thread's step, ``Poller.poll``, is called by the test with an injected clock, so
nothing sleeps. Notices and task reports are read from the stream the SDK's ``Reporter``
writes, with the capabilities the host agreed to, as a host would see them; ``serve`` runs
over ``StringIO`` with the polls scripted between the requests.
"""

import io
import json
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast

import pytest
import watchdemo.plugin as plugin_module
from cmd_sdk import Copy, InvalidNoticeError, InvalidTaskError, Open, Plugin, Show, serve
from cmd_sdk.protocol import Agreement
from cmd_sdk.reporter import Reporter, installed
from watchdemo.keeper import STATE_FILE, Store
from watchdemo.plugin import Demo, home, plugin, query, run, start
from watchdemo.poller import Poller

URL = "https://example.test/PROJ-1"
INTERVAL = 5.0


def tickets_json(*entries: tuple[str, str, str] | tuple[str, str, str, str]) -> str:
    return json.dumps([
        {"id": e[0], "title": e[1], "status": e[2], **({"url": e[3]} if len(e) == 4 else {})}
        for e in entries
    ])


BASE = tickets_json(
    ("PROJ-1", "Fix the login page", "Open", URL),
    ("PROJ-2", "Login emails bounce", "In Review"),
    ("OPS-10", "Rotate the keys", "Done"),
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class Rig:
    """A plugin, its poller and the stream the SDK writes, over a temporary tickets file."""

    demo: Demo
    poller: Poller
    clock: Clock
    tickets: Path
    data: Path
    sink: io.StringIO
    reporter: Reporter

    def edit(self, text: str) -> None:
        self.tickets.write_text(text, encoding="utf-8")

    def poll(self, after: float = INTERVAL) -> None:
        """One tick of the thread, ``after`` seconds since the last."""
        self.clock.sleep(after)
        with installed(self.reporter):
            self.poller.poll()

    def written(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.sink.getvalue().splitlines()]

    def notices(self) -> list[dict[str, Any]]:
        return [line["params"] for line in self.written() if line.get("event") == "notify"]

    def tasks(self) -> list[dict[str, Any]]:
        return [line["params"] for line in self.written() if line.get("event") == "task"]

    def watch(self, ticket_id: str) -> None:
        assert isinstance(run(self.demo, ticket_id, "watch"), Show)


def rig(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *capabilities: str,
    tickets: str | None = BASE,
    config: str | None = None,
    state: dict[str, Any] | None = None,
) -> Rig:
    data, conf = tmp_path / "data", tmp_path / "config"
    data.mkdir()
    conf.mkdir()
    path = tmp_path / "tickets.json"
    if tickets is not None:
        path.write_text(tickets, encoding="utf-8")
    text = f'tickets = "{path}"\n' if config is None else config.replace("PATH", str(path))
    (conf / "config.toml").write_text(text, encoding="utf-8")
    if state is not None:
        (data / STATE_FILE).write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setenv("CMD_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(conf))
    demo = start()
    clock = Clock()
    ticks = iter(range(1, 10_000))
    poller = Poller(
        path,
        INTERVAL,
        demo.store,
        clock=clock,
        wall=lambda: f"2026-10-14T19:00:{next(ticks) % 60:02d}",
    )
    sink = io.StringIO()
    reporter = Reporter(sink)
    reporter.agree(Agreement(1, frozenset(capabilities)))
    return Rig(demo, poller, clock, path, data, sink, reporter)


# --- rows --------------------------------------------------------------------------------


def test_a_query_finds_tickets_by_id_and_by_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    assert [i.id for i in query(r.demo, "ops")] == ["OPS-10"]
    assert [i.id for i in query(r.demo, "LOGIN")] == ["PROJ-2", "PROJ-1"]
    assert [i.id for i in query(r.demo, "PROJ-1 ")] == ["PROJ-1"]


def test_the_toggle_follows_what_is_watched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    (item,) = query(r.demo, "PROJ-1")
    assert [a.id for a in item.actions] == ["open", "watch", "copy"]
    r.watch("PROJ-1")
    (item,) = query(r.demo, "PROJ-1")
    assert [a.id for a in item.actions] == ["open", "unwatch", "copy"]
    assert item.subtitle == "Open · watching"


def test_after_tab_the_toggle_is_the_default_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The window runs only a row's first action until DRAFT-6, so Tab then Enter must watch.
    r = rig(tmp_path, monkeypatch)
    (item,) = query(r.demo, "PROJ-1 ")
    assert [a.id for a in item.actions] == ["watch", "open", "copy"]
    r.watch("PROJ-1")
    (item,) = query(r.demo, "PROJ-1 ")
    assert [a.id for a in item.actions] == ["unwatch", "open", "copy"]


def test_watching_lists_what_is_watched_with_the_status_the_file_has_now(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    r.watch("PROJ-2")
    r.edit(tickets_json(("PROJ-2", "Login emails bounce", "Done")))
    assert [(i.id, i.subtitle) for i in query(r.demo, "watching")] == [
        ("PROJ-2", "Done · watching")
    ]
    suggestion = query(r.demo, "")[-1]
    assert (suggestion.title, suggestion.complete, suggestion.actions) == (
        "Watching (1)",
        "watch watching",
        (),
    )


@pytest.mark.parametrize("tickets", [None, "{", "[1]", '{"id": 1}'])
def test_a_missing_or_invalid_tickets_file_is_a_row_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tickets: str | None
) -> None:
    r = rig(tmp_path, monkeypatch, tickets=tickets)
    for items in (query(r.demo, "x"), query(r.demo, ""), home(r.demo)):
        assert items
        assert str(r.tickets) in items[0].title
        assert items[0].actions == ()


@pytest.mark.parametrize("config", [None, "tickets = 5\n", "tickets = [", "interval = 2\n"])
def test_missing_or_bad_config_is_a_row_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: str | None
) -> None:
    if config is None:  # no config.toml at all
        rig(tmp_path, monkeypatch, config="")
        (tmp_path / "config" / "config.toml").unlink()
        demo = start()
    else:
        demo = rig(tmp_path, monkeypatch, config=config).demo
    assert demo.settings.tickets is None
    (item, *_) = query(demo, "x")
    assert item.actions == ()
    assert item.complete is None
    assert "tickets" in item.title or "config.toml" in item.title
    assert isinstance(run(demo, "", "default"), Show)
    # Not set up (no file, or only an interval) is silent on home; a wrong config is shown.
    assert bool(home(demo)) is (config in {"tickets = 5\n", "tickets = ["})


def test_a_missing_data_directory_variable_still_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    monkeypatch.delenv("CMD_PLUGIN_DATA")
    demo = start()
    assert demo.settings.tickets == str(r.tickets)
    assert isinstance(run(demo, "PROJ-1", "watch"), Show)
    assert [i.id for i in query(demo, "watching")] == ["PROJ-1"]


# --- run ---------------------------------------------------------------------------------


def test_open_goes_to_the_url_or_copies_the_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    assert run(r.demo, "PROJ-1", "open") == Open(target=URL)
    assert run(r.demo, "PROJ-2", "open") == Copy(text="PROJ-2")
    assert run(r.demo, "PROJ-1", "copy") == Copy(text="PROJ-1")


def test_watch_and_unwatch_persist_across_a_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    assert run(r.demo, "PROJ-1", "watch") == Show(text="Watching PROJ-1")
    assert Store.load(r.data).state.watched == {"PROJ-1"}
    assert run(r.demo, "PROJ-1", "unwatch") == Show(text="Stopped watching PROJ-1")
    assert Store.load(r.data).state.watched == frozenset()


def test_watching_a_ticket_that_is_not_in_the_file_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    assert run(r.demo, "NOPE-1", "watch") == Show(text="NOPE-1 is not in the tickets file")
    assert run(r.demo, "NOPE-1", "open") == Show(text="NOPE-1 is not in the tickets file")
    assert not (r.data / STATE_FILE).exists()


def test_a_ticket_gone_from_the_file_can_still_be_unwatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    r.watch("PROJ-1")
    r.edit(tickets_json(("OPS-10", "Rotate the keys", "Done")))
    assert [i.id for i in query(r.demo, "watching")] == ["PROJ-1"]
    run(r.demo, "PROJ-1", "unwatch")
    assert query(r.demo, "watching")[0].title == "Nothing is watched yet"


def test_watch_with_the_file_unusable_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, tickets="{")
    effect = run(r.demo, "PROJ-1", "watch")
    assert isinstance(effect, Show)
    assert "not valid JSON" in effect.text


def test_an_unknown_action_is_a_line_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    assert run(r.demo, "PROJ-1", "explode") == Show(text="watchdemo has no action 'explode'")


# --- the poll ----------------------------------------------------------------------------


def test_a_changed_status_of_a_watched_ticket_is_one_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "notify")
    r.watch("PROJ-1")
    r.poll()
    assert r.notices() == []
    r.edit(BASE.replace('"Open"', '"In Review"'))
    r.poll()
    assert r.notices() == [
        {"id": "PROJ-1", "title": "PROJ-1 moved", "body": "Open -> In Review", "open": URL}
    ]
    r.poll()
    assert len(r.notices()) == 1  # the same status is not announced again


def test_a_notice_without_a_url_has_no_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "notify")
    r.watch("PROJ-2")
    r.edit(BASE.replace("In Review", "Done"))
    r.poll()
    assert r.notices() == [{"id": "PROJ-2", "title": "PROJ-2 moved", "body": "In Review -> Done"}]


def test_a_ticket_that_is_not_watched_is_never_announced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "notify")
    r.watch("PROJ-1")
    r.poll()
    r.edit(BASE.replace("In Review", "Done").replace("Rotate", "Rotated"))
    r.poll()
    assert r.notices() == []


def test_the_first_sight_of_a_watched_ticket_is_recorded_without_a_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = {"version": 1, "watched": ["PROJ-1"], "seen": {}, "recent": []}
    r = rig(tmp_path, monkeypatch, "notify", state=state)
    r.poll()
    assert r.notices() == []
    assert Store.load(r.data).state.seen == {"PROJ-1": "Open"}
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    assert [n["body"] for n in r.notices()] == ["Open -> Done"]


def test_a_restart_does_not_announce_old_changes_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "notify")
    r.watch("PROJ-1")
    r.poll()
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    assert len(r.notices()) == 1
    again = Poller(r.tickets, INTERVAL, Store.load(r.data), clock=r.clock, wall=lambda: "later")
    with installed(r.reporter):
        again.poll()
    assert len(r.notices()) == 1


def test_a_change_made_while_the_plugin_was_stopped_is_announced_on_its_first_poll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "notify")
    r.watch("PROJ-1")
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    assert [n["body"] for n in r.notices()] == ["Open -> Done"]


def test_many_changes_after_a_long_gap_are_one_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    many = [(f"T-{n}", f"Ticket {n}", "Open") for n in range(6)]
    r = rig(tmp_path, monkeypatch, "notify", tickets=tickets_json(*many))
    for ticket_id, _, _ in many:
        r.watch(ticket_id)
    r.poll()
    r.edit(tickets_json(*[(i, t, "Done") for i, t, _ in many]))
    r.poll(after=4 * INTERVAL)  # the Mac slept
    assert r.notices() == [
        {"id": "summary", "title": "6 tickets moved", "body": "T-0, T-1, T-2, T-3, T-4 and 1 more"}
    ]
    assert len(Store.load(r.data).state.recent) == 6  # all six are still on the list


def test_the_same_changes_in_an_ordinary_poll_are_one_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    many = [(f"T-{n}", f"Ticket {n}", "Open") for n in range(6)]
    r = rig(tmp_path, monkeypatch, "notify", tickets=tickets_json(*many))
    for ticket_id, _, _ in many:
        r.watch(ticket_id)
    r.poll()
    r.edit(tickets_json(*[(i, t, "Done") for i, t, _ in many]))
    r.poll()
    assert [n["id"] for n in r.notices()] == [f"T-{n}" for n in range(6)]


def test_a_long_gap_with_few_changes_is_still_one_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    many = [(f"T-{n}", f"Ticket {n}", "Open") for n in range(3)]
    r = rig(tmp_path, monkeypatch, "notify", tickets=tickets_json(*many))
    for ticket_id, _, _ in many:
        r.watch(ticket_id)
    r.edit(tickets_json(*[(i, t, "Done") for i, t, _ in many]))
    r.poll(after=100 * INTERVAL)
    assert len(r.notices()) == 3


def test_an_unreadable_file_is_one_failed_task_until_it_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "tasks", "notify")
    r.watch("PROJ-1")
    r.poll()
    assert r.tasks() == []  # healthy: nothing to say
    r.edit("{ not json")
    for _ in range(4):
        r.poll()
    failed = r.tasks()
    assert len(failed) == 1
    assert failed[0]["id"] == "source"
    assert failed[0]["label"] == "Tickets file"
    assert failed[0]["state"] == "failed"
    assert "is not valid JSON" in failed[0]["detail"]
    r.edit(BASE)
    r.poll()
    r.poll()
    assert [t["state"] for t in r.tasks()] == ["failed", "done"]
    assert r.notices() == []  # no notice for any of it
    r.edit("[]")
    r.poll()
    r.edit("nope")
    r.poll()
    assert [t["state"] for t in r.tasks()] == ["failed", "done", "failed"]


@pytest.mark.parametrize(
    "broken",
    [
        '{"id": "A"}',
        '[{"id": "A"}]',
        "[1, 2]",
        '[{"id":"A","title":"t","status":"s"},{"id":"A","title":"t","status":"s"}]',
        "",
    ],
)
def test_every_kind_of_invalid_file_is_the_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    r = rig(tmp_path, monkeypatch, "tasks")
    r.edit(broken)
    r.poll()
    (task,) = r.tasks()
    assert task["state"] == "failed"
    assert str(r.tickets) in task["detail"]


def test_a_missing_file_is_the_task_and_creating_it_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "tasks", tickets=None)
    r.poll()
    (task,) = r.tasks()
    assert "does not exist" in task["detail"]
    r.edit(BASE)
    r.poll()
    assert [t["state"] for t in r.tasks()] == ["failed", "done"]


def test_a_file_that_comes_back_after_an_outage_is_diffed_against_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, "notify", "tasks")
    r.watch("PROJ-1")
    r.poll()
    r.edit("garbage")
    r.poll()
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    assert [n["body"] for n in r.notices()] == ["Open -> Done"]


def test_a_host_that_named_neither_capability_gets_nothing_and_the_plugin_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    r.watch("PROJ-1")
    r.poll()
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    r.edit("broken")
    r.poll()
    assert not r.sink.getvalue()
    recent = Store.load(r.data).state.recent
    assert [(c.id, c.old, c.new) for c in recent] == [("PROJ-1", "Open", "Done")]
    titles = [i.title for i in home(r.demo)]
    assert "is not valid JSON" in titles[0]
    assert titles[1:] == ["PROJ-1: Open -> Done"]


@pytest.mark.parametrize(("named", "notices", "tasks"), [("tasks", 0, 1), ("notify", 1, 0)])
def test_each_capability_gates_only_its_own_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, named: str, notices: int, tasks: int
) -> None:
    r = rig(tmp_path, monkeypatch, named)
    r.watch("PROJ-1")
    r.poll()
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    r.edit("broken")
    r.poll()
    assert (len(r.notices()), len(r.tasks())) == (notices, tasks)


def test_home_shows_what_moved_newest_first_then_what_is_watched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    r.watch("PROJ-1")
    r.watch("PROJ-2")
    r.poll()
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    r.edit(BASE.replace('"Open"', '"Done"').replace("In Review", "Blocked"))
    r.poll()
    assert [i.title for i in home(r.demo)] == [
        "PROJ-2: In Review -> Blocked",
        "PROJ-1: Open -> Done",
        "PROJ-1  Fix the login page",
        "PROJ-2  Login emails bounce",
    ]


def test_corrupt_state_is_noted_once_and_the_plugin_starts_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    r = rig(tmp_path, monkeypatch)
    (r.data / STATE_FILE).write_text("}{", encoding="utf-8")
    demo = start()
    assert capsys.readouterr().err.count("started with nothing watched") == 1
    assert demo.store.state.watched == frozenset()
    assert any("started with nothing watched" in i.title for i in home(demo))
    query(demo, "x")
    home(demo)
    assert not capsys.readouterr().err


def test_the_poll_never_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    r = rig(tmp_path, monkeypatch, "notify", "tasks")

    def explode(_state: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(r.demo.store, "transact", explode)
    r.poll()
    assert "RuntimeError: boom" in capsys.readouterr().err


def test_an_invalid_notice_is_logged_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    r = rig(tmp_path, monkeypatch, "notify")
    r.watch("PROJ-1")
    r.poll()

    def refuse(*_args: object) -> None:
        raise InvalidNoticeError("title must not be empty")

    monkeypatch.setattr("watchdemo.poller.notify", refuse)
    r.edit(BASE.replace('"Open"', '"Done"'))
    r.poll()
    assert "cannot notify about PROJ-1" in capsys.readouterr().err


def test_an_invalid_task_is_logged_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    r = rig(tmp_path, monkeypatch, "tasks")

    def refuse(*_args: object) -> None:
        raise InvalidTaskError("bad")

    monkeypatch.setattr("watchdemo.poller.report", refuse)
    r.edit("nope")
    r.poll()
    assert "cannot report source" in capsys.readouterr().err


def test_the_thread_polls_until_it_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    polled = threading.Event()
    calls: list[float] = []

    def clock() -> float:
        calls.append(0.0)
        if len(calls) >= 3:
            polled.set()
        return float(len(calls))

    poller = Poller(r.tickets, 0.01, r.demo.store, clock=clock)
    stop = poller.start()
    assert polled.wait(5)
    thread = next(t for t in threading.enumerate() if t.name == "watchdemo-poll")
    assert thread.daemon
    stop.set()
    thread.join(5)
    assert not thread.is_alive()


def test_main_starts_the_poller_when_the_host_describes_and_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, config='tickets = "PATH"\ninterval = 0.1\n')
    seen: list[Any] = []
    served: list[Plugin] = []

    class FakePoller:
        def __init__(self, path: Path, interval: float, store: Store) -> None:
            seen.append((path, interval, store))

        def start(self) -> None:
            seen.append(("started", self))

    monkeypatch.setattr(plugin_module, "Poller", FakePoller)
    monkeypatch.setattr(plugin_module, "serve", served.append)
    plugin_module.main()
    assert seen[0][:2] == (r.tickets, 0.5)  # raised to the minimum
    assert seen[1:] == []  # not before the host has described: nobody could hear it yet
    (served_plugin,) = served
    assert served_plugin.description.keyword == "watch"
    assert served_plugin.description.home is True
    assert served_plugin.describe is not None
    agreement = Agreement(1, frozenset({"tasks", "notify"}))
    served_plugin.describe(agreement)
    served_plugin.describe(agreement)
    assert [entry[0] for entry in seen[1:]] == ["started"]


def test_main_starts_no_poller_without_a_tickets_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig(tmp_path, monkeypatch, config="")
    seen: list[Any] = []

    class FakePoller:
        def __init__(self, *_args: object) -> None:
            seen.append("made")

    monkeypatch.setattr(plugin_module, "Poller", FakePoller)
    monkeypatch.setattr(plugin_module, "serve", lambda _p: seen.append("served"))
    plugin_module.main()
    assert seen == ["served"]


# --- over the protocol -------------------------------------------------------------------


class Script:
    """The host's side of the conversation: requests, with the test's steps between them.

    ``serve`` reads it line by line; a step runs when ``serve`` asks for the next line, that
    is after the previous request was answered, on ``serve``'s thread and inside its reporter.
    """

    def __init__(
        self, capabilities: list[str], steps: list[dict[str, Any] | Callable[[], None]]
    ) -> None:
        self._capabilities = capabilities
        self._steps = steps

    def __iter__(self) -> Iterator[str]:
        yield self._line(1, "describe", {"protocol": 1, "capabilities": self._capabilities})
        number = 1
        for step in self._steps:
            if callable(step):
                step()
            else:
                number += 1
                yield self._line(number, step["method"], step["params"])

    @staticmethod
    def _line(number: int, method: str, params: dict[str, Any]) -> str:
        return json.dumps({"id": number, "method": method, "params": params}) + "\n"


def converse(
    demo: Demo, capabilities: list[str], *steps: dict[str, Any] | Callable[[], None]
) -> list[dict[str, Any]]:
    sink = io.StringIO()
    serve(plugin(demo), cast("TextIO", Script(capabilities, list(steps))), sink)
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def ask(text: str) -> dict[str, Any]:
    return {"method": "query", "params": {"text": text}}


def act(item: str, action: str) -> dict[str, Any]:
    return {"method": "run", "params": {"item": item, "action": action}}


HOME = {"method": "query", "params": {"text": "", "home": True}}


def test_over_the_protocol_a_ticket_is_found_watched_changed_and_told(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)

    def moved() -> None:
        r.edit(BASE.replace('"Open"', '"In Review"'))
        r.clock.sleep(INTERVAL)
        r.poller.poll()

    def settled() -> None:
        r.clock.sleep(INTERVAL)
        r.poller.poll()

    out = converse(
        r.demo,
        ["tasks", "notify"],
        ask("login"),
        act("PROJ-1", "watch"),
        settled,
        moved,
        HOME,
        act("PROJ-1", "unwatch"),
    )
    answers = [o for o in out if "id" in o]
    describe, found, watched, home_answer, unwatched = answers
    assert describe["result"]["name"] == "watchdemo"
    assert [i["id"] for i in found["result"]["items"]] == ["PROJ-2", "PROJ-1"]
    ticket = found["result"]["items"][1]
    assert ticket["complete"] == "watch PROJ-1 "
    assert [a["id"] for a in ticket["actions"]] == ["open", "watch", "copy"]
    assert watched["result"]["effect"] == {"kind": "show", "text": "Watching PROJ-1"}
    assert home_answer["result"]["items"][0]["title"] == "PROJ-1: Open -> In Review"
    assert unwatched["result"]["effect"]["text"] == "Stopped watching PROJ-1"
    events = [o for o in out if "event" in o]
    assert events == [
        {
            "event": "notify",
            "params": {
                "id": "PROJ-1",
                "title": "PROJ-1 moved",
                "body": "Open -> In Review",
                "open": URL,
            },
        }
    ]
    # The notice arrives after the watch was answered and before the home query was.
    ids = [o.get("id", o.get("event")) for o in out]
    assert ids == [1, 2, 3, "notify", 4, 5]


def test_over_the_protocol_a_host_with_no_capabilities_hears_only_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)

    def step() -> None:
        r.clock.sleep(INTERVAL)
        r.poller.poll()

    def move() -> None:
        r.edit(BASE.replace('"Open"', '"Done"'))
        step()

    def break_file() -> None:
        r.edit("broken")
        step()

    out = converse(r.demo, [], act("PROJ-1", "watch"), step, move, break_file, HOME)
    assert all("event" not in o for o in out)
    assert "error" not in json.dumps(out)
    titles = [i["title"] for i in out[-1]["result"]["items"]]
    assert "is not valid JSON" in titles[0]
    assert titles[1:] == ["PROJ-1: Open -> Done"]


def test_over_the_protocol_the_description_asks_for_the_home_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch)
    (describe, *_) = converse(r.demo, [], HOME)
    assert describe["result"]["keyword"] == "watch"
    assert describe["result"]["home"] is True


def test_home_is_empty_until_a_tickets_file_is_set_but_a_broken_one_is_shown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unset = rig(tmp_path, monkeypatch, config="")
    assert home(unset.demo) == ()
    assert query(unset.demo, "")  # typing the keyword still explains the setup
    other = tmp_path / "other"
    other.mkdir()
    broken = rig(other, monkeypatch, tickets="broken")
    assert home(broken.demo)  # a set file that cannot be read is a failure, not silence


def test_enter_on_the_setup_row_says_where_the_config_goes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = rig(tmp_path, monkeypatch, config="")
    effect = run(r.demo, "", "default")
    assert isinstance(effect, Show)
    assert str(tmp_path / "config" / "config.toml") in effect.text
