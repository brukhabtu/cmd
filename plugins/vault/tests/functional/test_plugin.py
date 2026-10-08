"""The plugin against a fake obsidian CLI, with the host's directories, the probe and the
clock faked at the boundary.

The fake CLI is ``fake_obsidian.py``, copied into a temporary directory and named by
``obsidian.bin`` in the config, as the real one would be. Whether Obsidian runs is the
probe's answer, injected; the outbox thread's steps are run in the test's own thread, except
in the one test that starts the real thread.
"""

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cmd_sdk import Close, Copy, Item, Open, Show
from vault.gateway import probe
from vault.outbox import Entry, writing
from vault.plugin import Vault, plugin, query, run, start
from vault.worker import Worker, step

_FAKE = Path(__file__).with_name("fake_obsidian.py")

CONFIG = """
[obsidian]
bin = "{bin}"
vault = "Work"

[obsidian.deadlines]
probe = 0.3
query = 0.5
write = 0.5
run = 0.5

[[capture]]
keyword = "todo"
kind = "append"
target = "@daily"
heading = "Tasks"
line = "- [ ] {{text}}"

[[capture]]
keyword = "note"
kind = "append"
target = "Inbox.md"
heading = "Captured"
line = "- {{time}} {{text}}"

[[capture]]
keyword = "1:1"
kind = "open"
target = "People/{{text}}.md"
template = "Person"

[[view]]
keyword = "find"
kind = "search"

[[view]]
keyword = "tasks"
kind = "tasks"
"""


@dataclass
class FakeObsidian:
    """The fake CLI, its vault, and whether the (injected) probe says Obsidian runs."""

    directory: Path
    vault: Path
    running: bool = True
    probes: int = 0

    @property
    def bin(self) -> Path:
        return self.directory / "obsidian"

    def mode(self, mode: str) -> None:
        state = {"mode": mode, "vault": str(self.vault)}
        (self.directory / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def calls(self) -> list[list[str]]:
        log = self.directory / "calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def commands(self) -> list[str]:
        """Each call's command, without the vault and the parameters."""
        return [next(word for word in call if "=" not in word) for call in self.calls()]

    def daily(self) -> str:
        today = datetime.now().astimezone().date().isoformat()
        path = self.vault / "Daily" / f"{today}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def note(self, relative: str) -> str:
        path = self.vault / relative
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def ask(self) -> bool:
        self.probes += 1
        return self.running


@dataclass
class Clock:
    """The time the plugin sees, moved by the test."""

    now: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)

    def ticks(self) -> float:
        return self.now.timestamp()


@dataclass
class Host:
    """The directories the host gives the plugin, and a way to start it as the host would."""

    data: Path
    config: Path
    fake: FakeObsidian
    clock: Clock

    def configure(self, text: str) -> None:
        self.config.mkdir(parents=True, exist_ok=True)
        (self.config / "config.toml").write_text(text, encoding="utf-8")

    def start(self) -> Vault:
        return start(ask=self.fake.ask, clock=self.clock, ticks=self.clock.ticks)

    def outbox(self) -> list[dict[str, object]]:
        directory = self.data / "outbox"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]


def _drain(vault: Vault, tries: int = 10) -> None:
    """Run the outbox thread's steps here, until one says nothing more is due now."""
    for _ in range(tries):
        wait = step(vault.outbox, vault.world)
        if wait is None or wait > 0:
            return


@pytest.fixture
def fake(tmp_path: Path) -> FakeObsidian:
    directory = tmp_path / "cli"
    directory.mkdir()
    vault = tmp_path / "vault"
    vault.mkdir()
    script = directory / "obsidian"
    script.write_text(f"#!{sys.executable}\n" + _FAKE.read_text(encoding="utf-8"), encoding="utf-8")
    script.chmod(0o755)
    obsidian = FakeObsidian(directory, vault)
    obsidian.mode("working")
    return obsidian


@pytest.fixture
def host(tmp_path: Path, fake: FakeObsidian, monkeypatch: pytest.MonkeyPatch) -> Host:
    data = tmp_path / "data"
    data.mkdir()
    config = tmp_path / "config"
    monkeypatch.setenv("CMD_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(config))
    found = Host(data, config, fake, Clock())
    found.configure(CONFIG.format(bin=fake.bin))
    return found


def _capture(host: Host, text: str) -> tuple[Vault, Item]:
    vault = host.start()
    (row,) = [row for row in query(vault, text) if row.id.startswith("capture:")]
    assert run(vault, row.id, "default") == Close()
    return vault, row


# --- AC1: written to the configured target through the CLI, from config alone --------------


def test_a_todo_lands_in_todays_daily_note_under_its_heading(
    host: Host, fake: FakeObsidian
) -> None:
    (fake.vault / "Daily").mkdir()
    today = datetime.now().astimezone().date().isoformat()
    (fake.vault / "Daily" / f"{today}.md").write_text("# Tasks\n- [ ] old\n\n# Log\nx\n")
    vault, row = _capture(host, "todo call Sam about the offsite")
    assert row.title == "- [ ] call Sam about the offsite"
    assert row.subtitle == "todo: today's daily note, under Tasks"
    assert len(host.outbox()) == 1
    assert fake.calls() == []  # run queued it; it did not write
    _drain(vault)
    assert fake.daily() == "# Tasks\n- [ ] old\n- [ ] call Sam about the offsite\n\n# Log\nx\n"
    assert fake.calls() == [
        ["vault=Work", "daily:append", "content=- [ ] call Sam about the offsite", "heading=Tasks"]
    ]
    assert host.outbox() == []
    assert vault.outbox.entries() == ()


def test_a_note_creates_its_target_when_missing_then_appends_in_order(
    host: Host, fake: FakeObsidian
) -> None:
    vault, row = _capture(host, "note Priya wants the hiring plan by Friday")
    stamp = host.clock.now.strftime("%H:%M")
    assert row.title == f"- {stamp} Priya wants the hiring plan by Friday"
    assert row.subtitle == "note: Inbox.md, under Captured"
    assert run(vault, "capture:note second", "default") == Close()  # same instant: just after
    host.clock.advance(1)
    _drain(vault)
    assert fake.note("Inbox.md") == (
        f"## Captured\n- {stamp} Priya wants the hiring plan by Friday\n- {stamp} second\n"
    )
    assert fake.commands() == ["read", "create", "append", "read", "append"]
    assert host.outbox() == []


def test_every_value_comes_from_the_config(host: Host, fake: FakeObsidian) -> None:
    host.configure(
        f"""
status_keyword = "obs"
date_format = "%d.%m.%Y"
[obsidian]
bin = "{fake.bin}"
[[capture]]
keyword = "Idea"
kind = "append"
target = "Ideas/{{date}} {{text}}.md"
template = "Idea"
line = "* {{text}} ({{date}})"
"""
    )
    vault, row = _capture(host, "idea  a: better/launcher ")
    date = host.clock.now.strftime("%d.%m.%Y")
    assert row.subtitle == f"Idea: Ideas/{date} a betterlauncher.md"
    _drain(vault)
    assert fake.note(f"Ideas/{date} a betterlauncher.md") == (
        f"made from Idea\n* a: better/launcher ({date})\n"
    )
    assert fake.calls()[1] == ["create", f"path=Ideas/{date} a betterlauncher.md", "template=Idea"]


def test_the_thread_writes_what_run_queued_without_being_driven(
    host: Host, fake: FakeObsidian
) -> None:
    vault = host.start()
    worker = Worker(vault.outbox, vault.world).start()
    try:
        assert run(vault, "capture:todo from the thread", "default") == Close()
        deadline = time.monotonic() + 10
        while vault.outbox.entries() and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        worker.stop(timeout=5)
    assert "- [ ] from the thread" in fake.daily()
    assert host.outbox() == []


def test_the_keyword_alone_explains_and_enter_asks_for_text(host: Host) -> None:
    vault = host.start()
    (row, *_) = query(vault, "todo")
    assert row.title == "todo <text>"
    assert row.subtitle == "Adds a line to today's daily note, under Tasks"
    assert run(vault, row.id, "default") == Show(text="Type the text after todo")
    assert run(vault, "capture:todo ", "default") == Show(text="Type the text after todo")
    assert host.outbox() == []


# --- AC2: closed, slow or failing, the capture stays and is written once -----------------


def test_while_obsidian_is_not_running_nothing_is_called_and_nothing_is_lost(
    host: Host, fake: FakeObsidian
) -> None:
    fake.running = False
    vault, row = _capture(host, "todo wait for it")
    assert row.subtitle is not None
    assert row.subtitle.endswith("Obsidian is not running: kept until it opens")
    for _ in range(3):
        _drain(vault)
        host.clock.advance(60)
    assert fake.calls() == []
    (entry,) = host.outbox()
    assert entry["state"] == "pending"
    assert entry["attempts"] == 0  # a closed Obsidian costs no tries
    fake.running = True
    _drain(vault)
    assert fake.daily().count("- [ ] wait for it") == 1
    assert host.outbox() == []


def test_a_closed_cli_keeps_the_entry_and_it_is_written_once_on_recovery(
    host: Host, fake: FakeObsidian
) -> None:
    fake.mode("closed")
    vault, _ = _capture(host, "todo after the outage")
    _drain(vault)
    (entry,) = host.outbox()
    assert entry["state"] == "pending"
    assert entry["attempts"] == 1
    assert (
        entry["last_error"]
        == "append: Error: Obsidian is not running. Open Obsidian and try again."
    )
    rows = query(vault, "todo")
    assert rows[-1].title == "Waiting: - [ ] after the outage"
    assert rows[-1].subtitle is not None
    assert rows[-1].subtitle.startswith("try 2 of 5 at ")
    _drain(vault)
    assert len(fake.calls()) == 1  # not due again for 5 s
    fake.mode("working")
    host.clock.advance(5)
    _drain(vault)
    assert fake.daily().count("- [ ] after the outage") == 1
    assert host.outbox() == []


def test_a_failing_cli_fails_the_entry_on_the_fifth_try_and_retry_writes_it_once(
    host: Host, fake: FakeObsidian
) -> None:
    fake.mode("failing")
    vault, _ = _capture(host, "todo stubborn")
    for wait in (5, 30, 120, 600, 0):
        _drain(vault)
        host.clock.advance(wait)
    (entry,) = host.outbox()
    assert entry["state"] == "failed"
    assert entry["attempts"] == 5
    assert entry["last_error"] == "append: Error: something went wrong in the vault"
    assert len(fake.calls()) == 5
    row = next(row for row in query(vault, "vault") if row.id.startswith("outbox:"))
    assert row.title == "Not written: - [ ] stubborn"
    assert [action.id for action in row.actions] == ["retry", "copy", "discard"]
    assert run(vault, row.id, "copy") == Copy(text="- [ ] stubborn")
    fake.mode("working")
    assert run(vault, row.id, "default") == Close()  # Retry
    _drain(vault)
    assert fake.daily().count("- [ ] stubborn") == 1
    assert host.outbox() == []


def test_a_slow_write_that_did_not_land_is_checked_then_written_once(
    host: Host, fake: FakeObsidian
) -> None:
    fake.mode("slow")
    vault, _ = _capture(host, "todo slowly")
    started = time.monotonic()
    _drain(vault)
    assert time.monotonic() - started < 3
    (entry,) = host.outbox()
    assert entry["state"] == "unknown"
    assert entry["last_error"] == "append: Obsidian did not answer within 0.5 s"
    row = next(row for row in query(vault, "vault") if row.id.startswith("outbox:"))
    assert row.title == "Checking: - [ ] slowly"
    assert [action.id for action in row.actions] == ["retry", "copy", "discard"]
    fake.mode("working")
    host.clock.advance(5)
    _drain(vault)
    assert fake.commands() == ["daily:append", "daily:read", "daily:append"]
    assert fake.daily().count("- [ ] slowly") == 1
    assert host.outbox() == []


def test_a_slow_write_that_landed_is_found_by_the_check_and_not_written_again(
    host: Host, fake: FakeObsidian
) -> None:
    fake.mode("landing")
    vault, _ = _capture(host, "todo landed anyway")
    _drain(vault)
    assert host.outbox()[0]["state"] == "unknown"
    fake.mode("working")
    host.clock.advance(5)
    _drain(vault)
    assert fake.commands() == ["daily:append", "daily:read"]
    assert fake.daily().count("- [ ] landed anyway") == 1
    assert host.outbox() == []


def test_a_note_whose_create_was_killed_is_checked_and_not_created_twice(
    host: Host, fake: FakeObsidian
) -> None:
    fake.mode("landing")
    vault, _ = _capture(host, "note first words")
    _drain(vault)
    assert fake.commands() == ["read", "create"]
    assert host.outbox()[0]["state"] == "unknown"
    fake.mode("working")
    host.clock.advance(5)
    _drain(vault)
    assert fake.commands() == ["read", "create", "read", "append"]
    assert fake.note("Inbox.md").count("first words") == 1


def test_an_entry_left_writing_by_a_crash_is_checked_at_start_and_not_written_twice(
    host: Host, fake: FakeObsidian
) -> None:
    vault, _ = _capture(host, "todo before the crash")
    (entry,) = vault.outbox.entries()
    # The CLI wrote the line, then the plugin died before deleting the entry it had marked.
    fake.mode("working")
    today = datetime.now().astimezone().date().isoformat()
    (fake.vault / "Daily").mkdir()
    (fake.vault / "Daily" / f"{today}.md").write_text("## Tasks\n- [ ] before the crash\n")
    path = host.data / "outbox" / f"{entry.id}.json"
    on_disk = json.loads(path.read_text())
    on_disk["state"] = "writing"
    path.write_text(json.dumps(on_disk))

    restarted = host.start()
    assert json.loads(path.read_text())["state"] == "unknown"
    _drain(restarted)
    assert fake.commands() == ["daily:read"]
    assert fake.daily().count("- [ ] before the crash") == 1
    assert host.outbox() == []


def test_writing_is_on_disk_before_the_cli_is_called(host: Host, fake: FakeObsidian) -> None:
    fake.mode("slow")
    vault, _ = _capture(host, "todo watch the file")
    seen: list[str] = []
    original = vault.outbox.update

    def spy(entry: Entry, *, unless_writing: bool = False) -> bool:
        changed = original(entry, unless_writing=unless_writing)
        seen.append(str(host.outbox()[0]["state"]))
        seen.append(str(len(fake.calls())))
        return changed

    vault.outbox.update = spy  # type: ignore[method-assign]
    _drain(vault)
    assert seen[:2] == ["writing", "0"]


def test_discard_deletes_the_entry_and_a_writing_entry_cannot_be_changed(
    host: Host, fake: FakeObsidian
) -> None:
    fake.running = False
    vault, _ = _capture(host, "todo never mind")
    (entry,) = vault.outbox.entries()
    row = next(row for row in query(vault, "todo") if row.id.startswith("outbox:"))
    assert row.subtitle == "todo, today's daily note: Obsidian is not running"
    assert [action.id for action in row.actions] == ["copy", "discard"]
    assert run(vault, row.id, "discard") == Close()
    assert host.outbox() == []
    assert run(vault, row.id, "copy") == Show(text="That entry is gone: written or discarded")

    _capture(host, "todo busy")
    vault = host.start()
    (entry,) = vault.outbox.entries()
    vault.outbox.update(writing(entry))
    effect = run(vault, f"outbox:{entry.id}", "discard")
    assert effect == Show(text="It is being written now; look again in a moment")
    assert len(host.outbox()) == 1


def test_more_than_three_waiting_entries_point_at_the_status_keyword(
    host: Host, fake: FakeObsidian
) -> None:
    fake.running = False
    vault = host.start()
    for number in range(5):
        assert run(vault, f"capture:todo item {number}", "default") == Close()
        host.clock.advance(1)
    rows = query(vault, "todo x")
    assert [row.title for row in rows[1:]] == [
        "Waiting: - [ ] item 0",
        "Waiting: - [ ] item 1",
        "Waiting: - [ ] item 2",
        "2 more: type vault",
    ]
    assert len([row for row in query(vault, "vault") if row.id.startswith("outbox:")]) == 5


# --- AC3: query never raises, never calls the CLI while Obsidian is not running, and returns
# --- within the host's timeout --------------------------------------------------------------


HOST_QUERY_TIMEOUT = 3.0


def test_text_that_is_not_a_keyword_gets_nothing_without_a_probe_or_a_call(
    host: Host, fake: FakeObsidian
) -> None:
    vault = host.start()
    for text in ("", "   ", "2+2", "f readme", "todolist", "web vault"):
        assert query(vault, text) == ()
    assert fake.probes == 0
    assert fake.calls() == []


def test_while_obsidian_is_not_running_no_keyword_calls_the_cli(
    host: Host, fake: FakeObsidian
) -> None:
    fake.running = False
    vault = host.start()
    assert run(vault, "capture:todo queued", "default") == Close()
    for text in ("todo x", "note y", "find z", "vault", "tasks q", "1:1 Sam", "TODO x"):
        assert query(vault, text)
    (row, *_) = query(vault, "find budget")
    assert row.title == "Obsidian is not running"
    assert run(vault, row.id, "default") == Open(target="file:///Applications/Obsidian.app")
    _drain(vault)
    assert fake.calls() == []


def test_a_search_while_obsidian_runs_lists_notes_and_enter_opens_one(
    host: Host, fake: FakeObsidian
) -> None:
    (fake.vault / "Projects").mkdir()
    (fake.vault / "Projects" / "Budget 2027.md").write_text("numbers")
    (fake.vault / "Inbox.md").write_text("the budget is late")
    vault = host.start()
    rows = query(vault, "find budget")
    assert [(row.title, row.subtitle) for row in rows] == [
        ("Inbox", "the vault's top folder"),
        ("Budget 2027", "Projects"),
    ]
    assert fake.calls() == [["vault=Work", "search", "query=budget", "limit=20"]]
    query(vault, "find budget")
    assert len(fake.calls()) == 1  # kept 10 s
    assert run(vault, rows[1].id, "default") == Close()
    assert fake.calls()[-1] == ["vault=Work", "open", "path=Projects/Budget 2027.md"]
    assert query(vault, "find nothing-matches") == (query(vault, "find nothing-matches")[0],)
    assert query(vault, "find nothing-matches")[0].title == "No notes match 'nothing-matches'"


def test_a_slow_search_answers_within_the_host_timeout_with_the_reason(
    host: Host, fake: FakeObsidian
) -> None:
    fake.mode("slow")
    vault = host.start()
    started = time.monotonic()
    (row,) = query(vault, "find budget")
    assert time.monotonic() - started < HOST_QUERY_TIMEOUT
    assert row.title == "Obsidian did not answer within 0.5 s"


def test_a_failing_search_shows_the_first_line_of_the_error(host: Host, fake: FakeObsidian) -> None:
    fake.mode("failing")
    (row,) = query(host.start(), "find budget")
    assert row.title == "Error: something went wrong in the vault"


def test_a_capture_row_never_calls_the_cli_even_while_obsidian_runs(
    host: Host, fake: FakeObsidian
) -> None:
    vault = host.start()
    query(vault, "todo x")
    query(vault, "note y")
    query(vault, "vault")
    assert fake.calls() == []


def test_query_never_raises(host: Host, fake: FakeObsidian) -> None:
    def broken() -> bool:
        raise RuntimeError("the probe broke")

    vault = start(ask=broken, clock=host.clock, ticks=host.clock.ticks)
    (row,) = query(vault, "todo x")
    assert row.title == "vault: RuntimeError: the probe broke"
    assert query(vault, "unrelated words") == ()
    fake.bin.unlink()
    working = host.start()
    rows = query(working, "find budget")
    assert rows[0].title == "Search needs a usable obsidian.bin"
    assert rows[1].title == f"obsidian.bin: {fake.bin} is not an executable file"
    assert query(working, "todo x")[1].title == rows[1].title  # on every keyword


def test_the_real_probe_says_no_for_a_process_that_does_not_run() -> None:
    started = time.monotonic()
    assert probe("no-such-process-for-the-vault-tests", 0.3) is False
    assert time.monotonic() - started < 2


# --- the config's rows --------------------------------------------------------------------


def test_no_config_says_where_to_put_one_and_enter_opens_that_directory(host: Host) -> None:
    (host.config / "config.toml").unlink()
    host.config.rmdir()
    vault = host.start()
    assert query(vault, "todo x") == ()
    rows = query(vault, "vault")
    assert rows[1].title == f"No config: create config.toml in {host.config}"
    assert run(vault, rows[1].id, "default") == Open(target=host.config.as_uri())
    assert host.config.is_dir()


def test_an_unparsable_config_shows_on_the_keywords_of_the_last_one_that_parsed(
    host: Host,
) -> None:
    host.start()
    host.configure("[obsidian\nbin = 1")
    vault = host.start()
    (row, *_) = query(vault, "todo x")
    assert "is not valid TOML" in row.title
    assert row.title.endswith("nothing is captured until this is fixed")
    assert query(vault, "find x")[0].title == row.title
    assert any("is not valid TOML" in row.title for row in query(vault, "vault"))
    assert run(vault, "capture:todo x", "default") == Show(text="vault has no capture 'todo'")


def test_an_entry_of_a_kind_not_built_yet_says_so_and_captures_nothing(host: Host) -> None:
    vault = host.start()
    (row,) = query(vault, "1:1 Sam Lee")
    assert row.title == "1:1: a capture of kind 'open' is not built yet"
    assert run(vault, row.id, "default") == Show(text=row.title)
    (row,) = query(vault, "tasks")
    assert row.title == "tasks: a view of kind 'tasks' is not built yet"
    titles = [row.title for row in query(vault, "vault")]
    assert "1:1: a capture of kind 'open' is not built yet" in titles
    assert host.outbox() == []


def test_a_bad_entry_is_dropped_with_its_problem_and_the_rest_work(
    host: Host, fake: FakeObsidian
) -> None:
    host.configure(
        f"""
[obsidian]
bin = "{fake.bin}"
[obsidian.deadlines]
write = 99
[[capture]]
keyword = "todo"
kind = "append"
target = "@daily"
lines = "- {{text}}"
[[capture]]
keyword = "note"
kind = "append"
target = "Inbox.md"
"""
    )
    vault = host.start()
    assert [row.title for row in query(vault, "todo x")] == [
        "todo: lines: not a key a [[capture]] has"
    ]
    assert query(vault, "note x")[0].title == "- x"
    titles = [row.title for row in query(vault, "vault")]
    assert "obsidian.deadlines.write: must be at most 30.0 s; using 5.0" in titles


def test_without_the_hosts_variables_the_status_keyword_names_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CMD_PLUGIN_DATA", raising=False)
    monkeypatch.delenv("CMD_PLUGIN_CONFIG", raising=False)
    vault = start(ask=lambda: False)
    titles = [row.title for row in query(vault, "vault")]
    assert any("CMD_PLUGIN_DATA" in title for title in titles)
    assert any("CMD_PLUGIN_CONFIG" in title for title in titles)
    assert query(vault, "todo x") == ()


def test_the_plugin_speaks_the_protocol_without_a_keyword(host: Host) -> None:
    described = plugin(host.start()).description
    assert described.name == "vault"
    assert described.keyword is None
