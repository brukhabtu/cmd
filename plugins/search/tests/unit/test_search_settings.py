"""The config schema (decision 11's list, item 6): every key's default and rule, and both of
the decision's TOML examples parsing into the settings expected."""

import tomllib
from typing import Any

import pytest
from search.kinds import command, qmd
from search.settings import (
    Problem,
    Provider,
    Settings,
    command_line,
    file_url,
    fill_open,
    fold,
    parse,
    unusable,
)

WORKED = """
status_keyword = "search"
deadline = 1.0
min_chars = 2

[[provider]]
name = "qmd"
kind = "qmd"
keywords = ["n", "qmd"]
bin = "/opt/homebrew/bin/qmd"
env = { PATH = "/opt/homebrew/bin:/usr/bin:/bin" }
collections = ["notes", "meetings"]
mode = "search"
limit = 10
open = "obsidian://open?path={path}"

[[provider]]
name = "notes-rg"
kind = "command"
keywords = ["n", "grep"]
command = [
  "/opt/homebrew/bin/rg", "--files-with-matches", "--null", "--ignore-case",
  "--fixed-strings", "--sortr", "modified", "--glob", "*.{md,txt}",
  "--", "{text}", "/Users/bruk/Notes",
]
format = "paths"
exit_codes = [0, 1]
limit = 10
"""

SMALLEST = """
[[provider]]
name = "qmd"
kind = "qmd"
keywords = ["n"]
bin = "/opt/homebrew/bin/qmd"
env = { PATH = "/opt/homebrew/bin:/usr/bin:/bin" }
"""

QMD = {"name": "qmd", "kind": "qmd", "keywords": ["n"], "bin": "/q"}
RG = {
    "name": "rg",
    "kind": "command",
    "keywords": ["n"],
    "command": ["/rg", "{text}"],
    "format": "paths",
}


def _with(**changes: Any) -> dict[str, Any]:
    table = dict(QMD)
    for key, value in changes.items():
        if value is None:
            table.pop(key, None)
        else:
            table[key] = value
    return table


def _one(table: dict[str, Any]) -> Settings:
    return parse({"provider": [table]})


def _problems(settings: Settings) -> list[str]:
    return [problem.message for problem in settings.problems]


# --- the worked examples -------------------------------------------------------------------------


def test_the_worked_example_parses_into_two_providers_sharing_n() -> None:
    settings = parse(tomllib.loads(WORKED))
    assert settings.problems == ()
    assert (settings.status_keyword, settings.deadline, settings.min_chars) == ("search", 1.0, 2)
    first, second = settings.providers
    assert first == Provider(
        name="qmd",
        kind="qmd",
        keywords=("n", "qmd"),
        settings=qmd.Settings("/opt/homebrew/bin/qmd", ("notes", "meetings")),
        env=(("PATH", "/opt/homebrew/bin:/usr/bin:/bin"),),
        limit=10,
        open="obsidian://open?path={path}",
        reference="Copy docid",
    )
    assert second.settings == command.Settings(
        "/opt/homebrew/bin/rg",
        (
            "--files-with-matches", "--null", "--ignore-case", "--fixed-strings", "--sortr",
            "modified", "--glob", "*.{md,txt}", "--", "{text}", "/Users/bruk/Notes",
        ),
        "paths",
        frozenset({0, 1}),
    )  # fmt: skip
    assert second.reference == "Copy reference"
    assert first.answers("N")
    assert second.answers("n")
    assert not first.answers("grep")
    assert settings.keywords() == ("search", "n", "qmd", "grep")


def test_the_smallest_config_takes_every_default() -> None:
    settings = parse(tomllib.loads(SMALLEST))
    assert settings.problems == ()
    (provider,) = settings.providers
    assert provider.limit == 10
    assert provider.open == "{uri}"
    assert provider.settings == qmd.Settings("/opt/homebrew/bin/qmd")
    assert command_line(provider, "offsite") == (
        "/usr/bin/env", "PATH=/opt/homebrew/bin:/usr/bin:/bin", "/opt/homebrew/bin/qmd",
        "search", "--json", "--full-path", "-n", "10", "--", "offsite",
    )  # fmt: skip


# --- the top level ------------------------------------------------------------------------------


def test_the_top_level_defaults() -> None:
    settings = parse({"provider": [QMD]})
    assert (settings.status_keyword, settings.deadline, settings.min_chars) == ("search", 1.0, 2)


@pytest.mark.parametrize(
    ("raw", "expected", "message"),
    [
        (
            {"deadline": 0.4},
            ("search", 1.0, 2),
            "deadline: must be seconds from 0.5 to 1.5; using 1.0",
        ),
        (
            {"deadline": 2},
            ("search", 1.0, 2),
            "deadline: must be seconds from 0.5 to 1.5; using 1.0",
        ),
        (
            {"deadline": True},
            ("search", 1.0, 2),
            "deadline: must be seconds from 0.5 to 1.5; using 1.0",
        ),
        (
            {"min_chars": 0},
            ("search", 1.0, 2),
            "min_chars: must be a whole number from 1 to 10; using 2",
        ),
        (
            {"min_chars": 2.5},
            ("search", 1.0, 2),
            "min_chars: must be a whole number from 1 to 10; using 2",
        ),
        (
            {"status_keyword": "two words"},
            ("search", 1.0, 2),
            "status_keyword: must be one word; using 'search'",
        ),
    ],
)
def test_an_out_of_range_value_falls_back_to_its_default(
    raw: dict[str, Any], expected: tuple[str, float, int], message: str
) -> None:
    settings = parse({**raw, "provider": [QMD]})
    assert (settings.status_keyword, settings.deadline, settings.min_chars) == expected
    assert _problems(settings) == [message]
    assert len(settings.providers) == 1


def test_values_in_range_are_kept() -> None:
    settings = parse({"status_keyword": "find", "deadline": 1.5, "min_chars": 1, "provider": [QMD]})
    assert (settings.status_keyword, settings.deadline, settings.min_chars) == ("find", 1.5, 1)


def test_an_unknown_top_level_key_is_a_problem() -> None:
    assert _problems(parse({"provders": [], "provider": [QMD]})) == [
        "provders: not a key this config has"
    ]


def test_no_provider_is_a_problem_on_the_status_keyword() -> None:
    assert parse({}).problems == (Problem("no [[provider]]: add one to config.toml"),)
    assert _problems(parse({"provider": {"name": "x"}})) == [
        "provider: must be an array of tables, [[provider]]"
    ]


# --- a provider -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (_with(name=None), "provider 1: name: must be letters, digits, '.', '_' or '-'"),
        (_with(name="my qmd"), "provider 1: name: must be letters, digits, '.', '_' or '-'"),
        (_with(name="x" * 33), "x" * 33 + ": name: must be at most 32 characters"),
        (_with(kind=None), 'qmd: kind: must be set; it is "qmd" or "command"'),
        (_with(kind="grep"), 'qmd: kind: \'grep\' is not known; it is "qmd" or "command"'),
        (_with(keywords=None), "qmd: keywords: must be a list of one or more words"),
        (_with(keywords=[]), "qmd: keywords: must be a list of one or more words"),
        (_with(keywords="n"), "qmd: keywords: must be a list of one or more words"),
        (_with(keywords=["two words"]), "qmd: keywords: must be a list of one or more words"),
        (_with(keywords=["n", "Search"]), "qmd: keywords: 'Search' is the status keyword"),
        (_with(env="PATH=/bin"), "qmd: env: must be a table of text"),
        (_with(env={"1PATH": "/bin"}), "qmd: env: '1PATH' is not a variable's name"),
        (_with(env={"PATH": 3}), "qmd: env.PATH: must be text"),
        (_with(limit=0), "qmd: limit: must be a whole number from 1 to 50"),
        (_with(limit=51), "qmd: limit: must be a whole number from 1 to 50"),
        (_with(limit=True), "qmd: limit: must be a whole number from 1 to 50"),
        (
            _with(open="obsidian://open?line={line}"),
            "qmd: open: must be text holding {uri} or {path}",
        ),
        (_with(open="{path}"), "qmd: open: must be a URL with a scheme once filled"),
        (_with(bin=None), "qmd: bin: must be set, to an absolute path"),
        (_with(mode="query"), 'qmd: mode: "query" loads language models on every search'),
        (_with(mode="vsearch"), 'qmd: mode: "vsearch" loads language models on every search'),
        (_with(mode="fast"), "qmd: mode: 'fast' is not known; it is \"search\""),
        (_with(colections=["x"]), "qmd: colections: not a key a qmd provider has"),
        (_with(format="paths"), "qmd: format: not a key a qmd provider has"),
    ],
)
def test_an_invalid_provider_is_dropped_with_its_problem(
    table: dict[str, Any], message: str
) -> None:
    settings = _one(table)
    assert settings.providers == ()
    (problem,) = _problems(settings)
    assert problem.startswith(message)


def test_an_invalid_provider_does_not_stop_a_valid_one_and_shows_on_its_keywords() -> None:
    settings = parse({"provider": [_with(name="bad", keywords=["n", "Bad"], limit=0), RG]})
    assert [provider.name for provider in settings.providers] == ["rg"]
    (problem,) = settings.problems
    assert problem.keywords == ("n", "bad")
    assert problem.message == "bad: limit: must be a whole number from 1 to 50"


def test_a_repeated_name_is_refused_case_ignored() -> None:
    settings = parse({"provider": [QMD, _with(name="QMD")]})
    assert len(settings.providers) == 1
    assert _problems(settings) == ["QMD: name: another provider has it"]


def test_providers_may_share_a_keyword() -> None:
    settings = parse({"provider": [QMD, RG]})
    assert settings.problems == ()
    assert [provider.name for provider in settings.providers if provider.answers("n")] == [
        "qmd",
        "rg",
    ]


def test_a_keyword_equal_to_a_changed_status_keyword_is_refused() -> None:
    settings = parse({"status_keyword": "find", "provider": [_with(keywords=["FIND"])]})
    assert _problems(settings) == ["qmd: keywords: 'FIND' is the status keyword"]


def test_the_open_template_is_filled_once_with_each_placeholder() -> None:
    path = "/Users/bruk/My Notes/a#b%c.md"
    assert fill_open("{uri}", path, None) == "file:///Users/bruk/My%20Notes/a%23b%25c.md"
    assert (
        fill_open("obsidian://open?path={path}&line={line}", path, 4)
        == "obsidian://open?path=/Users/bruk/My%20Notes/a%23b%25c.md&line=4"
    )
    assert fill_open("x://{path}?{line}{other}", "/a/{line}", None) == "x:///a/%7Bline%7D?1{other}"
    assert file_url("/a/caf\udce9") == "file:///a/caf%E9"


def test_a_program_that_is_not_executable_keeps_the_provider_and_shows_on_its_keywords() -> None:
    settings = unusable(parse({"provider": [QMD, RG]}), "qmd", "qmd: /q is not an executable file")
    assert settings.providers[0].unusable == "qmd: /q is not an executable file"
    assert settings.providers[1].unusable is None
    assert settings.problems == (Problem("qmd: /q is not an executable file", ("n",)),)


def test_fold_lowers_ascii_alone() -> None:
    assert fold("ÉcoLE") == "École"
