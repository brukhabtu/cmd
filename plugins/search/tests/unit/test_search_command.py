"""The command kind on its own (decision 11's list, item 5)."""

import os
from pathlib import Path

import pytest
from cmd_sdk import CallResult
from search.hits import Failed, Found, Hit, InvalidError
from search.kinds import KINDS, command

PATHS = command.Settings(program="/usr/bin/rg", arguments=("--", "{text}", "/n"), format="paths")
HITS = command.Settings(program="/bin/tool", arguments=("{text}",), format="hits")
CWD = Path("/")


def _done(stdout: bytes, returncode: int = 0, stderr: bytes = b"") -> CallResult:
    return CallResult(returncode, stdout, stderr, timed_out=False)


def _cut(stdout: bytes) -> CallResult:
    return CallResult(None, stdout, b"", timed_out=True)


# --- the arguments -----------------------------------------------------------------------------


def test_text_and_limit_are_filled_and_other_braces_left_alone() -> None:
    settings = command.Settings(
        program="/usr/bin/rg",
        arguments=("--max-count", "{limit}", "--glob", "*.{md,txt}", "--", "{text}", "{other}"),
        format="paths",
    )
    assert command.arguments(settings, "offsite", 7) == (
        "--max-count", "7", "--glob", "*.{md,txt}", "--", "offsite", "{other}",
    )  # fmt: skip


def test_each_placeholder_is_filled_once_so_a_typed_placeholder_stays() -> None:
    settings = command.Settings(program="/t", arguments=("q={text}&n={limit}",), format="paths")
    assert command.arguments(settings, "{limit} {text}", 3) == ("q={limit} {text}&n=3",)


def test_text_is_required_in_some_argument() -> None:
    with pytest.raises(InvalidError, match=r"no argument holds \{text\}"):
        command.parse({"command": ["/usr/bin/rg", "--", "x"], "format": "paths"})
    with pytest.raises(InvalidError, match=r"no argument holds \{text\}"):
        command.parse({"command": ["/usr/bin/{text}"], "format": "paths"})


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ({"format": "paths"}, "command: must be set, a list: the program, then its arguments"),
        ({"command": "rg {text}", "format": "paths"}, "command: must be a list of text"),
        ({"command": ["rg", "{text}"], "format": "paths"}, "command: 'rg' is not an absolute path"),
        ({"command": ["/r=g", "{text}"], "format": "paths"}, "command: '/r=g' holds '='"),
        ({"command": ["/rg", "{text}"]}, 'format: must be set; it is "paths" or "hits"'),
        ({"command": ["/rg", "{text}"], "format": "json"}, "format: 'json' is not known"),
        ({"command": ["/rg", "{text}"], "format": "paths", "exit_codes": []}, "exit_codes"),
        ({"command": ["/rg", "{text}"], "format": "paths", "exit_codes": [256]}, "exit_codes"),
        ({"command": ["/rg", "{text}"], "format": "paths", "exit_codes": [True]}, "exit_codes"),
    ],
)
def test_bad_command_keys_are_refused(table: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidError) as caught:
        command.parse(table)
    assert str(caught.value).startswith(message)


def test_a_good_table_parses() -> None:
    settings = command.parse({
        "command": ["/usr/bin/rg", "--", "{text}"],
        "format": "paths",
        "exit_codes": [0, 1],
    })
    assert settings == command.Settings("/usr/bin/rg", ("--", "{text}"), "paths", frozenset({0, 1}))
    assert command.executable(settings) == "/usr/bin/rg"
    assert KINDS["command"] is command
    assert command.REFERENCE == "Copy reference"


# --- paths ------------------------------------------------------------------------------------------


def test_paths_split_by_newline_in_order() -> None:
    found = command.read(PATHS, _done(b"/n/b.md\n/n/a.md\n"), CWD, 10)
    assert found == Found((Hit("b.md", path="/n/b.md"), Hit("a.md", path="/n/a.md")))


def test_paths_split_by_nul_when_the_output_holds_one() -> None:
    found = command.read(PATHS, _done(b"/n/a\nb.md\0/n/c.md\0"), CWD, 10)
    assert isinstance(found, Found)
    assert [hit.path for hit in found.hits] == ["/n/a\nb.md", "/n/c.md"]


def test_a_last_line_without_a_newline_counts_when_the_command_finished() -> None:
    found = command.read(PATHS, _done(b"/n/a.md\n/n/b.md"), CWD, 10)
    assert isinstance(found, Found)
    assert [hit.path for hit in found.hits] == ["/n/a.md", "/n/b.md"]


def test_a_relative_path_is_skipped_and_counted() -> None:
    found = command.read(PATHS, _done(b"notes/a.md\n/n/b.md\n"), CWD, 10)
    assert found == Found(
        (Hit("b.md", path="/n/b.md"),),
        skipped=1,
        problem="'notes/a.md' is not an absolute path",
    )


def test_a_name_that_is_not_utf8_still_names_its_file() -> None:
    found = command.read(PATHS, _done(b"/n/caf\xe9.md\n"), CWD, 10)
    assert isinstance(found, Found)
    (hit,) = found.hits
    assert hit.path is not None
    assert os.fsencode(hit.path) == b"/n/caf\xe9.md"
    assert hit.title == "caf�.md"


def test_at_the_deadline_complete_lines_are_kept_and_the_answer_is_cut() -> None:
    found = command.read(PATHS, _cut(b"/n/a.md\n/n/b.md\n/n/hal"), CWD, 10)
    assert isinstance(found, Found)
    assert [hit.path for hit in found.hits] == ["/n/a.md", "/n/b.md"]
    assert found.cut


def test_no_more_than_four_entries_per_hit_are_read() -> None:
    lines = b"".join(b"rel/%d\n" % n for n in range(20)) + b"/n/late.md\n"
    found = command.read(PATHS, _done(lines), CWD, 2)
    assert found == Failed("8 entries are not paths: 'rel/0' is not an absolute path")


def test_no_more_hits_than_the_limit() -> None:
    found = command.read(PATHS, _done(b"/a\n/b\n/c\n"), CWD, 2)
    assert isinstance(found, Found)
    assert len(found.hits) == 2


# --- hits -------------------------------------------------------------------------------------------


def test_hits_as_one_array() -> None:
    answer = (
        b'[{"title": "Offsite budget", "path": "/Users/bruk/Notes/offsite.md", "line": 3,'
        b' "snippet": "Budget  approved\\nby finance.", "score": 9},'
        b' {"title": "Ticket", "url": "https://example.com/t/1", "reference": "T-1"}]'
    )
    found = command.read(HITS, _done(answer), CWD, 10)
    assert found == Found((
        Hit(
            "Offsite budget",
            path="/Users/bruk/Notes/offsite.md",
            line=3,
            snippet="Budget approved by finance.",
        ),
        Hit("Ticket", url="https://example.com/t/1", reference="T-1"),
    ))


def test_hits_as_json_lines_with_a_bad_entry_skipped_and_counted() -> None:
    answer = b'{"path": "/n/a.md"}\nnot json\n{"title": "Only a title"}\n{"path": "rel.md"}\n'
    found = command.read(HITS, _done(answer), CWD, 10)
    assert isinstance(found, Found)
    assert found.hits == (Hit("a.md", path="/n/a.md"), Hit("Only a title"))
    assert found.skipped == 2
    assert found.problem.startswith("a line is not JSON")


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        (b"3", "an entry is not an object"),
        (b"{}", "an entry has neither a title nor a path"),
        (b'{"title": "t", "url": "no-scheme"}', "url: 'no-scheme' has no scheme"),
        (b'{"title": "t", "line": 0}', "line: 0 is not a line number"),
        (b'{"title": "t", "snippet": 3}', "snippet: must be text"),
        (b'{"title": ""}', "title: must be text"),
    ],
)
def test_entries_that_do_not_fit_are_skipped(line: bytes, problem: str) -> None:
    found = command.read(HITS, _done(line + b'\n{"title": "ok"}\n'), CWD, 10)
    assert found == Found((Hit("ok"),), skipped=1, problem=problem)


def test_all_entries_bad_is_failed() -> None:
    found = command.read(HITS, _done(b"nope\nnope\n"), CWD, 10)
    assert isinstance(found, Failed)
    assert found.message.startswith("2 entries are not hits: a line is not JSON")


def test_an_array_that_does_not_parse_is_failed() -> None:
    found = command.read(HITS, _done(b'[{"title": "a"},'), CWD, 10)
    assert isinstance(found, Failed)
    assert found.message.startswith("answer is not a JSON array of hits")


def test_json_lines_cut_at_the_deadline_keep_their_complete_lines() -> None:
    found = command.read(HITS, _cut(b'{"title": "a"}\n{"title": "b'), CWD, 10)
    assert found == Found((Hit("a"),), cut=True)


def test_an_array_cut_at_the_deadline_is_failed() -> None:
    found = command.read(HITS, _cut(b'[{"title": "a"}, {"tit'), CWD, 10)
    assert isinstance(found, Failed)


# --- exit codes ---------------------------------------------------------------------------------------


def test_an_exit_code_in_exit_codes_is_an_answer() -> None:
    settings = command.Settings("/usr/bin/rg", ("{text}",), "paths", frozenset({0, 1}))
    assert command.read(settings, _done(b"", 1), CWD, 10) == Found(())


def test_an_exit_code_outside_exit_codes_is_failed_with_stderrs_first_line() -> None:
    stderr = b"\nrg: /nowhere: No such file or directory (os error 2)\nmore\n"
    assert command.read(PATHS, _done(b"", 2, stderr), CWD, 10) == Failed(
        "rg: /nowhere: No such file or directory (os error 2)"
    )


def test_exit_2_with_some_hits_keeps_them_beside_the_failure() -> None:
    found = command.read(PATHS, _done(b"/n/a.md\n", 2, b"rg: /locked: denied\n"), CWD, 10)
    assert found == Found((Hit("a.md", path="/n/a.md"),), failure=Failed("rg: /locked: denied"))


def test_a_failure_with_nothing_on_stderr_names_the_exit() -> None:
    assert command.read(PATHS, _done(b"", 5), CWD, 10) == Failed("exited with 5")
