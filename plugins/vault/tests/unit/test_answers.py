from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from vault.answers import (
    Hits,
    Misconfigured,
    NotRunning,
    OnEntry,
    OpenApp,
    OpenConfig,
    OpenNote,
    Queue,
    Say,
    Startup,
    Status,
    ToCapture,
    ToView,
    Unanswered,
    Unbuilt,
    capture_rows,
    choice,
    entry_row,
    outbox_rows,
    route,
    status_rows,
    view_rows,
)
from vault.outbox import Entry, State, new_entry
from vault.schema import Capture, CaptureKind, Problem, Settings, View, ViewKind, parse

NOW = datetime(2026, 10, 8, 14, 30, 5, tzinfo=UTC)
TODO = Capture("todo", CaptureKind.APPEND, "@daily", None, "Tasks", "- [ ] {text}")
NOTE = Capture("note", CaptureKind.APPEND, "Inbox.md", None, None, "- {time} {text}")
ONE_ON_ONE = Capture("1:1", CaptureKind.OPEN, "People/{text}.md", "Person")
FIND = View("find", ViewKind.SEARCH)
TASKS = View("tasks", ViewKind.TASKS)
SETTINGS = Settings(captures=(TODO, NOTE, ONE_ON_ONE), views=(FIND, TASKS))
STARTUP = Startup(SETTINGS)


def _entry(text: str = "call Sam", /, **changes: object) -> Entry:
    entry = new_entry(TODO, text, NOW, "3f9a1c", ("%Y-%m-%d", "%H:%M"))
    return replace(entry, **changes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("vault", Status()),
        ("  VAULT anything", Status()),
        ("todo  call Sam ", ToCapture(TODO, "call Sam")),
        ("ToDo", ToCapture(TODO, "")),
        ("note\tx", ToCapture(NOTE, "x")),
        ("find budget plan", ToView(FIND, "budget plan")),
        ("1:1 Sam", Unbuilt("1:1", "capture of kind 'open'")),
        ("tasks", Unbuilt("tasks", "view of kind 'tasks'")),
        ("", None),
        ("   ", None),
        ("todolist", None),
        ("2+2", None),
        ("web todo", None),
    ],
)
def test_the_first_word_picks_the_keyword_with_ascii_case_ignored(
    text: str, expected: object
) -> None:
    assert route(text, STARTUP) == expected


def test_a_dropped_entry_still_answers_on_its_keyword_with_its_problem() -> None:
    settings = parse({"obsidian": {"bin": "/o"}, "capture": [{"keyword": "todo", "kind": "nope"}]})
    assert route("todo x", Startup(settings)) == Misconfigured(
        "todo", ('todo: kind: must be "append" or "open"',)
    )


def test_an_unreadable_config_answers_on_the_keywords_that_last_parsed() -> None:
    startup = Startup(
        Settings(), unreadable="config.toml is not valid TOML", stale_keywords=("todo",)
    )
    assert route("todo x", startup) == Misconfigured(
        "todo", ("config.toml is not valid TOML; nothing is captured until this is fixed",)
    )
    assert route("note x", startup) is None


def test_a_capture_row_shows_the_line_and_where_it_goes() -> None:
    (row,) = capture_rows(ToCapture(NOTE, "Priya: plan"), SETTINGS, NOW, running=True)
    assert (row.id, row.title, row.subtitle) == (
        "capture:note Priya: plan",
        "- 14:30 Priya: plan",
        "note: Inbox.md",
    )
    (row,) = capture_rows(ToCapture(TODO, "x"), SETTINGS, NOW, running=False)
    assert row.subtitle == (
        "todo: today's daily note, under Tasks; Obsidian is not running: kept until it opens"
    )
    (row,) = capture_rows(ToCapture(TODO, ""), SETTINGS, NOW, running=True)
    assert (row.title, row.subtitle) == (
        "todo <text>",
        "Adds a line to today's daily note, under Tasks",
    )
    assert choice(row.id) == Say("Type the text after todo")


def test_view_rows_for_each_answer() -> None:
    (hint,) = view_rows(ToView(FIND, ""), None)
    assert hint.title == "Search the vault"
    (row,) = view_rows(ToView(FIND, "x"), NotRunning())
    assert (row.title, choice(row.id)) == ("Obsidian is not running", OpenApp())
    (row,) = view_rows(ToView(FIND, "x"), Unanswered("Obsidian did not answer within 1.5 s"))
    assert row.title == "Obsidian did not answer within 1.5 s"
    (row,) = view_rows(ToView(FIND, "x"), Hits(()))
    assert row.title == "No notes match 'x'"
    rows = view_rows(ToView(FIND, "x"), Hits(("P/a.md", "b.md")))
    assert [(row.title, row.subtitle, choice(row.id)) for row in rows] == [
        ("a", "P", OpenNote("P/a.md")),
        ("b", "the vault's top folder", OpenNote("b.md")),
    ]


LATER = NOW + timedelta(seconds=5)


@pytest.mark.parametrize(
    ("changes", "running", "title", "subtitle", "actions"),
    [
        (
            {},
            False,
            "Waiting: - [ ] call Sam",
            "todo, today's daily note: Obsidian is not running",
            ["copy", "discard"],
        ),
        (
            {},
            True,
            "Waiting: - [ ] call Sam",
            "todo, today's daily note: next in line",
            ["copy", "discard"],
        ),
        (
            {"attempts": 1, "next_try": LATER, "last_error": "append: closed"},
            True,
            "Waiting: - [ ] call Sam",
            "try 2 of 5 at 14:30: append: closed",
            ["retry", "copy", "discard"],
        ),
        (
            {"state": State.WRITING},
            True,
            "Writing: - [ ] call Sam",
            "a call is in flight",
            ["copy"],
        ),
        (
            {"state": State.UNKNOWN},
            True,
            "Checking: - [ ] call Sam",
            "checking whether it landed",
            ["retry", "copy", "discard"],
        ),
        (
            {"state": State.UNKNOWN, "last_error": "read: busy"},
            True,
            "Checking: - [ ] call Sam",
            "read: busy",
            ["retry", "copy", "discard"],
        ),
        (
            {"state": State.FAILED, "last_error": "append: no"},
            True,
            "Not written: - [ ] call Sam",
            "append: no",
            ["retry", "copy", "discard"],
        ),
        (
            {"kind": CaptureKind.OPEN, "target": "People/Sam.md"},
            False,
            "Waiting: People/Sam.md",
            "todo, People/Sam.md: Obsidian is not running",
            ["copy", "discard"],
        ),
    ],
)
def test_an_outbox_entry_reads_as_decision_ten_says(
    changes: dict[str, object], running: bool, title: str, subtitle: str, actions: list[str]
) -> None:
    row = entry_row(_entry(**changes), "%H:%M", running=running)
    assert (row.title, row.subtitle, [action.id for action in row.actions]) == (
        title,
        subtitle,
        actions,
    )
    assert choice(row.id) == OnEntry("20261008T143005-3f9a1c")


def test_a_keyword_shows_three_entries_those_needing_the_person_first_then_how_many_more() -> None:
    entries = [
        _entry("a", id="a", created=NOW),
        _entry("b", id="b", created=NOW + timedelta(seconds=1)),
        _entry("c", id="c", created=NOW + timedelta(seconds=2), state=State.FAILED),
        _entry("d", id="d", created=NOW + timedelta(seconds=3)),
    ]
    rows = outbox_rows(entries, "vault", "%H:%M", running=True)
    assert [row.title for row in rows] == [
        "Not written: - [ ] c",
        "Waiting: - [ ] a",
        "Waiting: - [ ] b",
        "1 more: type vault",
    ]
    assert outbox_rows([], "vault", "%H:%M", running=True) == ()


def test_the_status_keyword_shows_obsidian_the_config_and_the_outbox() -> None:
    startup = Startup(
        replace(SETTINGS, problems=(Problem("obsidian.bin: must be set", everywhere=True),)),
        problems=("outbox: x.json is not an entry, and is left alone: bad",),
    )
    titles = [row.title for row in status_rows(startup, [_entry()], "%H:%M", running=False)]
    assert titles == [
        "Obsidian is not running",
        "outbox: x.json is not an entry, and is left alone: bad",
        "obsidian.bin: must be set",
        "1:1: a capture of kind 'open' is not built yet",
        "tasks: a view of kind 'tasks' is not built yet",
        "Waiting: - [ ] call Sam",
    ]


def test_with_nothing_to_report_the_status_keyword_lists_the_keywords() -> None:
    rows = status_rows(
        Startup(Settings(captures=(TODO,), views=(FIND,))), [], "%H:%M", running=True
    )
    assert [row.title for row in rows] == ["Obsidian is running", "Keywords: todo, find"]


def test_no_config_and_an_unreadable_one_say_what_to_do() -> None:
    (_, row) = status_rows(
        Startup(Settings(), config_directory="/c", no_config=True), [], "%H:%M", running=True
    )
    assert (row.title, choice(row.id)) == ("No config: create config.toml in /c", OpenConfig())
    (_, row) = status_rows(Startup(Settings(), unreadable="bad TOML"), [], "%H:%M", running=True)
    assert (row.title, row.subtitle) == ("bad TOML", "nothing is captured until this is fixed")


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ("capture:todo call Sam", Queue("todo", "call Sam")),
        ("capture:1:1 Sam Lee", Queue("1:1", "Sam Lee")),
        ("capture:todo", Queue("todo", "")),
        ("say:hello: there", Say("hello: there")),
        ("outbox:20261008T143005-3f9a1c", OnEntry("20261008T143005-3f9a1c")),
        ("note:a: b.md", OpenNote("a: b.md")),
        ("app:", OpenApp()),
        ("config:", OpenConfig()),
        ("elsewhere", Say("vault made no row 'elsewhere'")),
    ],
)
def test_an_id_says_what_enter_does(item: str, expected: object) -> None:
    assert choice(item) == expected
