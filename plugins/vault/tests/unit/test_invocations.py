from dataclasses import replace
from datetime import UTC, datetime

import pytest
from vault.invocations import (
    first_line,
    folder,
    found_paths,
    note_name,
    open_arguments,
    probe_arguments,
    says_missing,
    search_arguments,
    write_arguments,
)
from vault.outbox import Entry, Step, new_entry
from vault.schema import Capture, CaptureKind, Obsidian

OBSIDIAN = Obsidian(bin="/usr/local/bin/obsidian", vault="Work")
NOW = datetime(2026, 10, 8, 14, 30, tzinfo=UTC)
DAILY = new_entry(
    Capture("todo", CaptureKind.APPEND, "@daily", None, "Tasks", "- [ ] {text}"),
    "x",
    NOW,
    "000000",
    ("%Y-%m-%d", "%H:%M"),
)
INBOX = replace(DAILY, target="Inbox.md", heading=None, template="Inbox", line="- x")


@pytest.mark.parametrize(
    ("entry", "step", "arguments"),
    [
        (DAILY, Step.READ, ["daily:read"]),
        (DAILY, Step.APPEND, ["daily:append", "content=- [ ] x", "heading=Tasks"]),
        (INBOX, Step.READ, ["read", "path=Inbox.md"]),
        (INBOX, Step.CREATE, ["create", "path=Inbox.md", "template=Inbox"]),
        (INBOX, Step.APPEND, ["append", "path=Inbox.md", "content=- x"]),
    ],
)
def test_each_step_has_its_command_and_names_the_vault_first(
    entry: Entry, step: Step, arguments: list[str]
) -> None:
    assert write_arguments(OBSIDIAN, entry, step) == [
        "/usr/local/bin/obsidian",
        "vault=Work",
        *arguments,
    ]


def test_without_a_vault_the_clis_default_is_used() -> None:
    assert write_arguments(replace(OBSIDIAN, vault=None), DAILY, Step.READ) == [
        "/usr/local/bin/obsidian",
        "daily:read",
    ]


def test_search_open_and_the_probe() -> None:
    assert search_arguments(OBSIDIAN, "a b", 20)[2:] == ["search", "query=a b", "limit=20"]
    assert open_arguments(OBSIDIAN, "P/x.md")[2:] == ["open", "path=P/x.md"]
    assert probe_arguments("Obsidian") == ["/usr/bin/pgrep", "-x", "Obsidian"]


def test_a_search_answer_is_one_path_a_line() -> None:
    assert found_paths("a.md\n\n  b/c.md \nd.md\n", 2) == ("a.md", "b/c.md")
    assert found_paths("", 5) == ()


def test_the_first_line_of_an_error_or_a_fallback() -> None:
    assert first_line("\n  Error: closed  \nmore", "x") == "Error: closed"
    assert first_line("", "the CLI exited with 1") == "the CLI exited with 1"


@pytest.mark.parametrize(
    ("stderr", "missing"),
    [("Error: file not found: x", True), ("x does not exist", True), ("Error: closed", False)],
)
def test_a_missing_note_is_told_from_other_errors(stderr: str, missing: bool) -> None:
    assert says_missing(stderr) is missing


def test_a_note_is_shown_by_name_and_folder() -> None:
    assert (note_name("Projects/Budget.md"), folder("Projects/Budget.md")) == ("Budget", "Projects")
    assert (note_name("Inbox.md"), folder("Inbox.md")) == ("Inbox", "the vault's top folder")
