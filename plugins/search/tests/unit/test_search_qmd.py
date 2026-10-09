"""The qmd kind on its own: the captures of the real qmd 2.8.3 through ``read``, the snippet,
and the argv (decision 11's list, items 1 to 3).

The captures are in ``tests/fixtures/qmd``; the paths in them name the scratch directory of
the machine they were captured on, which is all they need to be.
"""

import json
from pathlib import Path

import pytest
from cmd_sdk import CallResult
from search.hits import Failed, Found, Hit, InvalidError
from search.kinds import KINDS, qmd
from search.schema import Provider, command_line

FIXTURES = Path(__file__).parent.parent / "fixtures" / "qmd"
SETTINGS = qmd.Settings(bin="/opt/homebrew/bin/qmd")
CWD = Path("/Users/bruk/Library/Application Support/cmd/plugins/search")


def _answer(name: str, returncode: int = 0) -> CallResult:
    return CallResult(returncode, (FIXTURES / name).read_bytes(), b"", timed_out=False)


def _error(name: str, returncode: int) -> CallResult:
    return CallResult(returncode, b"", (FIXTURES / name).read_bytes(), timed_out=False)


# --- 1. each capture through read -------------------------------------------------------------


def test_two_hits_keep_qmds_order_and_docids() -> None:
    found = qmd.read(SETTINGS, _answer("search-two-hits.json"), CWD, 10)
    assert isinstance(found, Found)
    assert found.hits == (
        Hit(
            title="Team offsite planning",
            url="qmd://notes/offsite.md",
            snippet="We want a two day offsite in March. Budget approved by finance. Venue"
            " shortlist: the lake house and the city loft.",
            line=1,
            reference="#75ebe1",
        ),
        Hit(
            title="Quarterly planning meeting",
            url="qmd://meetings/2026-10-01-planning.md",
            snippet="Timeline for the quarter: ship the launcher plugins, document the protocol,"
            " plan the offsite. Sam owns the timeline.",
            line=3,
            reference="#1f2c47",
        ),
    )
    assert found.skipped == 0


def test_one_hit() -> None:
    found = qmd.read(SETTINGS, _answer("search-one-hit.json"), CWD, 10)
    assert isinstance(found, Found)
    (hit,) = found.hits
    assert hit.title == "Hiring plan 2027"
    assert hit.reference == "#154360"
    assert hit.snippet.startswith("Two senior backend engineers")


def test_no_hits_is_an_empty_answer() -> None:
    assert qmd.read(SETTINGS, _answer("search-no-hits.json"), CWD, 10) == Found(())


def test_full_paths_are_paths_and_carry_no_docid() -> None:
    found = qmd.read(SETTINGS, _answer("search-two-hits-full-path.json"), CWD, 10)
    assert isinstance(found, Found)
    printed = json.loads((FIXTURES / "search-two-hits-full-path.json").read_text(encoding="utf-8"))
    assert [hit.path for hit in found.hits] == [entry["file"] for entry in printed]
    assert all(entry["file"].startswith("/") for entry in printed)
    assert [hit.reference for hit in found.hits] == [None, None]
    assert [hit.url for hit in found.hits] == [None, None]


def test_a_relative_path_is_resolved_against_the_working_directory_given() -> None:
    found = qmd.read(SETTINGS, _answer("search-full-path-under-cwd.json"), CWD, 10)
    assert isinstance(found, Found)
    assert [hit.path for hit in found.hits] == [
        f"{CWD}/notes/offsite.md",
        f"{CWD}/meetings/2026-10-01-planning.md",
    ]


def test_a_qmd_uri_is_a_hit_not_on_disk_with_its_docid() -> None:
    found = qmd.read(SETTINGS, _answer("search-one-hit.json"), CWD, 10)
    assert isinstance(found, Found)
    (hit,) = found.hits
    assert hit.path is None
    assert hit.url == "qmd://notes/hiring-plan.md"
    assert hit.reference == "#154360"


@pytest.mark.parametrize(
    ("capture", "code", "message"),
    [
        ("error-collection-not-found.txt", 1, "Collection not found: nosuchcollection"),
        ("error-usage.txt", 1, "Usage: qmd search [options] <query>"),
        ("error-no-node.txt", 127, "/usr/bin/env: 'node': No such file or directory"),
    ],
)
def test_each_stderr_capture_is_failed_with_its_line(capture: str, code: int, message: str) -> None:
    assert qmd.read(SETTINGS, _error(capture, code), CWD, 10) == Failed(message)


def test_a_failure_with_nothing_on_stderr_names_the_exit() -> None:
    assert qmd.read(SETTINGS, CallResult(3, b"", b"", timed_out=False), CWD, 10) == Failed(
        "exited with 3"
    )


def test_output_that_is_not_json_is_failed() -> None:
    outcome = qmd.read(SETTINGS, CallResult(0, b"Searching...", b"", timed_out=False), CWD, 10)
    assert isinstance(outcome, Failed)
    assert outcome.message.startswith("answer is not qmd's JSON: Expecting value")


def test_json_that_is_not_an_array_is_failed() -> None:
    outcome = qmd.read(SETTINGS, CallResult(0, b'{"a": 1}', b"", timed_out=False), CWD, 10)
    assert outcome == Failed("answer is not qmd's JSON: not an array")


def test_a_timed_out_call_is_failed_since_half_an_array_is_no_answer() -> None:
    half = (FIXTURES / "search-two-hits.json").read_bytes()[:200]
    outcome = qmd.read(SETTINGS, CallResult(None, half, b"", timed_out=True), CWD, 10)
    assert isinstance(outcome, Failed)


def test_an_entry_without_a_file_is_skipped_and_counted() -> None:
    answer = b'[{"title": "no file"}, 3, {"file": "notes/x.md"}, {"file": "/n/a.md"}]'
    found = qmd.read(SETTINGS, CallResult(0, answer, b"", timed_out=False), CWD, 10)
    assert isinstance(found, Found)
    assert found.hits == (Hit(title="a.md", path="/n/a.md"),)
    assert found.skipped == 3
    assert found.problem == "an entry has no file"


def test_the_score_and_context_are_ignored() -> None:
    answer = (
        b'[{"file": "/n/b.md", "score": 0}, {"file": "/n/a.md", "score": 0.49, "context": "x"}]'
    )
    found = qmd.read(SETTINGS, CallResult(0, answer, b"", timed_out=False), CWD, 10)
    assert isinstance(found, Found)
    assert [hit.path for hit in found.hits] == ["/n/b.md", "/n/a.md"]


def test_no_more_hits_than_the_limit_are_kept() -> None:
    answer = b"[" + b",".join(b'{"file": "/n/%d.md"}' % n for n in range(9)) + b"]"
    found = qmd.read(SETTINGS, CallResult(0, answer, b"", timed_out=False), CWD, 2)
    assert isinstance(found, Found)
    assert [hit.path for hit in found.hits] == ["/n/0.md", "/n/1.md"]


# --- 2. the snippet -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header", ["@@ -1,3 @@ (0 before, 1 after)", "@@ -12 @@ (2 before, 0 after)"]
)
def test_both_header_shapes_are_dropped(header: str) -> None:
    assert qmd.clean_snippet(f"{header}\nBudget approved.", "Offsite") == "Budget approved."


def test_the_title_line_and_blank_lines_are_dropped() -> None:
    snippet = "@@ -1,3 @@ (0 before, 1 after)\n# Offsite\n\nBudget   approved.\n\n"
    assert qmd.clean_snippet(snippet, "Offsite") == "Budget approved."


def test_a_snippet_without_a_header_is_left_whole() -> None:
    assert qmd.clean_snippet("@ not a header\nline two", "T") == "@ not a header line two"


def test_another_heading_is_kept() -> None:
    assert qmd.clean_snippet("# Other\nbody", "Offsite") == "# Other body"


# --- 3. the argv ----------------------------------------------------------------------------------


def _provider(settings: qmd.Settings, env: tuple[tuple[str, str], ...] = ()) -> Provider:
    return Provider(name="qmd", kind="qmd", keywords=("n",), settings=settings, env=env, limit=7)


def test_the_argv_puts_dash_dash_before_the_text_and_n_the_limit() -> None:
    assert command_line(_provider(SETTINGS), "offsite") == (
        "/opt/homebrew/bin/qmd", "search", "--json", "--full-path", "-n", "7", "--", "offsite",
    )  # fmt: skip


def test_a_text_starting_with_a_dash_still_follows_dash_dash() -> None:
    assert command_line(_provider(SETTINGS), "-offsite")[-2:] == ("--", "-offsite")


def test_one_c_per_collection_and_index_only_when_set() -> None:
    settings = qmd.Settings(bin="/q", collections=("notes", "meetings"), index="work")
    assert qmd.arguments(settings, "x", 10) == (
        "search", "--json", "--full-path", "-n", "10",
        "-c", "notes", "-c", "meetings", "--index", "work", "--", "x",
    )  # fmt: skip
    assert "--index" not in qmd.arguments(SETTINGS, "x", 10)


def test_env_puts_usr_bin_env_in_front_and_without_it_the_program_runs_bare() -> None:
    path = (("PATH", "/opt/homebrew/bin:/usr/bin:/bin"),)
    assert command_line(_provider(SETTINGS, path), "x")[:3] == (
        "/usr/bin/env",
        "PATH=/opt/homebrew/bin:/usr/bin:/bin",
        "/opt/homebrew/bin/qmd",
    )
    assert command_line(_provider(SETTINGS), "x")[0] == "/opt/homebrew/bin/qmd"


# --- the settings ---------------------------------------------------------------------------------


def test_the_kind_is_registered_under_its_name() -> None:
    assert KINDS["qmd"] is qmd
    assert qmd.REFERENCE == "Copy docid"


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ({}, "bin: must be set, to an absolute path"),
        ({"bin": "qmd"}, "bin: 'qmd' is not an absolute path"),
        ({"bin": "/a=b/qmd"}, "bin: '/a=b/qmd' holds '=', which env would take for a variable"),
        ({"bin": "/q", "collections": "notes"}, "collections: must be a list of text"),
        ({"bin": "/q", "collections": ["-x"]}, "collections: '-x' is not a collection's name"),
        ({"bin": "/q", "index": "my index"}, "index: must be letters, digits, '.', '_' or '-'"),
    ],
)
def test_bad_qmd_keys_are_refused(table: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidError) as caught:
        qmd.parse(table)
    assert str(caught.value) == message
