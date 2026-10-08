import tomllib

import pytest
from vault.schema import (
    Capture,
    CaptureKind,
    Deadlines,
    Problem,
    View,
    ViewKind,
    fold,
    parse,
    safe_in_path,
    without_bin,
)

FULL = """
status_keyword = "vault"
date_format = "%Y-%m-%d"
time_format = "%H:%M"

[obsidian]
bin = "/usr/local/bin/obsidian"
app = "/Applications/Obsidian.app"
process = "Obsidian"
vault = "Work"

[obsidian.deadlines]
probe = 0.3
query = 1.5
write = 5.0
run = 2.0

[[capture]]
keyword = "todo"
kind = "append"
target = "@daily"
heading = "Tasks"
line = "- [ ] {text}"

[[capture]]
keyword = "note"
kind = "append"
target = "Inbox.md"
heading = "Captured"
line = "- {time} {text}"

[[capture]]
keyword = "1:1"
kind = "open"
target = "People/{text}.md"
template = "Person"

[[view]]
keyword = "find"
kind = "search"

[[view]]
keyword = "tasks"
kind = "tasks"
limit = 30
"""

MINIMAL = {
    "obsidian": {"bin": "/usr/local/bin/obsidian"},
    "capture": [{"keyword": "todo", "kind": "append", "target": "@daily"}],
}


def _with_capture(**fields: object) -> dict[str, object]:
    entry = {"keyword": "todo", "kind": "append", "target": "@daily", **fields}
    return {
        "obsidian": {"bin": "/o"},
        "capture": [{k: v for k, v in entry.items() if v is not None}],
    }


def test_decision_tens_full_example_parses_without_a_problem() -> None:
    settings = parse(tomllib.loads(FULL))
    assert settings.problems == ()
    assert settings.obsidian.vault == "Work"
    assert settings.obsidian.deadlines == Deadlines(0.3, 1.5, 5.0, 2.0)
    assert settings.captures == (
        Capture("todo", CaptureKind.APPEND, "@daily", None, "Tasks", "- [ ] {text}"),
        Capture("note", CaptureKind.APPEND, "Inbox.md", None, "Captured", "- {time} {text}"),
        Capture("1:1", CaptureKind.OPEN, "People/{text}.md", "Person"),
    )
    assert settings.views == (View("find", ViewKind.SEARCH), View("tasks", ViewKind.TASKS, 30))
    assert settings.keywords() == ("vault", "todo", "note", "1:1", "find", "tasks")


def test_the_smallest_config_takes_every_default() -> None:
    settings = parse(MINIMAL)
    assert settings.problems == ()
    assert settings.status_keyword == "vault"
    assert settings.obsidian.app == "/Applications/Obsidian.app"
    assert settings.obsidian.process == "Obsidian"
    assert settings.obsidian.vault is None
    assert settings.obsidian.deadlines == Deadlines()
    assert settings.captures[0].line == "- {text}"


@pytest.mark.parametrize(
    ("fields", "problem"),
    [
        ({"heading": "#Tasks"}, "todo: heading: the heading's text, without #"),
        ({"line": "- no text"}, "todo: line: must contain {text}"),
        ({"line": "- {text} {when}"}, "todo: line: unknown placeholder {when}"),
        ({"line": "- {text!r}"}, "todo: line: '- {text!r}': a placeholder takes no format"),
        ({"line": "- {text"}, "todo: line: '- {text': expected '}' before end of string"),
        ({"line": "a\n{text}"}, "todo: line: must be one line of text"),
        (
            {"template": "Daily"},
            "todo: template: not with @daily, which uses the Daily notes template",
        ),
        (
            {"target": "/abs/x.md"},
            "todo: target: '/abs/x.md' must be @daily or a path inside the vault",
        ),
        (
            {"target": "../x.md"},
            "todo: target: '../x.md' must be @daily or a path inside the vault",
        ),
        ({"target": "Inbox.txt"}, "todo: target: 'Inbox.txt' must end in .md"),
        ({"target": "{time}.md"}, "todo: target: unknown placeholder {time}"),
        ({"target": ""}, "todo: target: must be set"),
        ({"kind": "prepend"}, 'todo: kind: must be "append" or "open"'),
        ({"kind": "open", "target": "@daily"}, 'todo: target: @daily is for kind = "append" only'),
        (
            {"kind": "open", "target": "P/{text}.md", "line": "{text}"},
            'todo: line: is for kind = "append" only',
        ),
        ({"colour": "red"}, "todo: colour: not a key a [[capture]] has"),
        ({"keyword": "two words"}, "a [[capture]]: keyword: must be one word"),
    ],
)
def test_an_invalid_capture_is_dropped_with_one_problem_on_its_keyword(
    fields: dict[str, object], problem: str
) -> None:
    settings = parse(_with_capture(**fields))
    assert settings.captures == ()
    (found,) = settings.problems
    assert found.message == problem
    assert found.everywhere is False


def test_a_keyword_is_unique_with_ascii_case_ignored_including_the_status_keyword() -> None:
    settings = parse({
        "obsidian": {"bin": "/o"},
        "capture": [
            {"keyword": "Vault", "kind": "append", "target": "@daily"},
            {"keyword": "todo", "kind": "append", "target": "@daily"},
            {"keyword": "TODO", "kind": "append", "target": "x.md"},
        ],
        "view": [{"keyword": "todo", "kind": "search"}],
    })
    assert [capture.keyword for capture in settings.captures] == ["todo"]
    assert settings.views == ()
    assert [problem.message for problem in settings.problems] == [
        "Vault: keyword: already used by another entry",
        "TODO: keyword: already used by another entry",
        "todo: keyword: already used by another entry",
    ]


@pytest.mark.parametrize(
    ("view", "problem"),
    [
        ({"kind": "browse"}, 'find: kind: must be "search" or "tasks"'),
        ({"kind": "search", "limit": 0}, "find: limit: must be a whole number from 1 to 50"),
        ({"kind": "search", "limit": 51}, "find: limit: must be a whole number from 1 to 50"),
        ({"kind": "search", "limit": True}, "find: limit: must be a whole number from 1 to 50"),
    ],
)
def test_an_invalid_view_is_dropped(view: dict[str, object], problem: str) -> None:
    settings = parse({"obsidian": {"bin": "/o"}, "view": [{"keyword": "find", **view}]})
    assert settings.views == ()
    assert [found.message for found in settings.problems] == [problem]


@pytest.mark.parametrize(
    ("obsidian", "problem"),
    [
        (None, "obsidian.bin: must be set, to the CLI's absolute path"),
        ({}, "obsidian.bin: must be set"),
        ({"bin": "obsidian"}, "obsidian.bin: 'obsidian' is not an absolute path"),
        ("x", "obsidian: must be a table, [obsidian]"),
    ],
)
def test_without_a_usable_bin_every_keyword_says_so_and_captures_are_kept(
    obsidian: object, problem: str
) -> None:
    raw = {"capture": MINIMAL["capture"]} | ({} if obsidian is None else {"obsidian": obsidian})
    settings = parse(raw)
    assert settings.obsidian.bin is None
    assert len(settings.captures) == 1
    assert settings.problems == (Problem(problem, everywhere=True),)


@pytest.mark.parametrize(
    ("deadlines", "expected", "problem"),
    [
        ({"write": 31}, Deadlines(), "obsidian.deadlines.write: must be at most 30.0 s; using 5.0"),
        ({"run": 9}, Deadlines(), "obsidian.deadlines.run: must be at most 8.0 s; using 2.0"),
        ({"probe": 0}, Deadlines(), "obsidian.deadlines.probe: must be seconds above 0; using 0.3"),
        (
            {"query": "1"},
            Deadlines(),
            "obsidian.deadlines.query: must be seconds above 0; using 1.5",
        ),
        (
            {"query": 1.6},
            Deadlines(),
            "obsidian.deadlines: probe + query must be at most 1.8 s; query uses 1.5 s",
        ),
        ({"query": 1.5, "probe": 0.3, "write": 30, "run": 8}, Deadlines(0.3, 1.5, 30.0, 8.0), None),
        ({"query": 0.5, "probe": 1.3}, Deadlines(1.3, 0.5), None),
    ],
)
def test_a_deadline_out_of_range_takes_its_default_and_says_so(
    deadlines: dict[str, object], expected: Deadlines, problem: str | None
) -> None:
    settings = parse({"obsidian": {"bin": "/o", "deadlines": deadlines}, "view": []})
    assert settings.obsidian.deadlines == expected
    assert [found.message for found in settings.problems] == ([problem] if problem else [])


def test_both_deadlines_fall_back_when_the_probe_alone_is_too_long() -> None:
    settings = parse({
        "obsidian": {"bin": "/o", "deadlines": {"probe": 1.7, "query": 0.5}},
        "view": [],
    })
    assert settings.obsidian.deadlines == Deadlines()


def test_unknown_keys_and_an_empty_config_are_problems_not_silence() -> None:
    settings = parse({"obsidian": {"bin": "/o", "colour": 1}, "captures": [], "statuskeyword": "v"})
    assert [problem.message for problem in settings.problems] == [
        "captures: not a key this config has",
        "statuskeyword: not a key this config has",
        "obsidian.colour: not a key this config has",
        "the config has no [[capture]] and no [[view]]",
    ]


def test_bad_top_level_values_fall_back_to_their_defaults() -> None:
    settings = parse({
        "status_keyword": "two words",
        "date_format": 3,
        "obsidian": {"bin": "/o", "app": "x"},
        "view": [],
    })
    assert settings.status_keyword == "vault"
    assert settings.date_format == "%Y-%m-%d"
    assert settings.obsidian.app == "/Applications/Obsidian.app"
    assert len(settings.problems) == 3


def test_a_refused_bin_is_shown_everywhere() -> None:
    settings = without_bin(parse(MINIMAL), "obsidian.bin: /x is not an executable file")
    assert settings.obsidian.bin is None
    assert settings.problems[-1] == Problem(
        "obsidian.bin: /x is not an executable file", everywhere=True
    )


def test_text_put_into_a_path_loses_what_obsidian_refuses_in_a_name() -> None:
    assert safe_in_path(' a\\b/c:d*e?f"g<h>i|j#k^l[m]n ') == "abcdefghijklmn"


def test_keywords_fold_ascii_case_only() -> None:
    assert fold("ToDo") == "todo"
    assert fold("ÉTÉ") == "ÉtÉ"
