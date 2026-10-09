"""Merging and rows (decision 11's list, items 4 and 8, and the row tables): rank over score,
the interleave, duplicates, problem rows after hits, the no-hits row, and the ids."""

import json
from pathlib import Path

from cmd_sdk import CallResult, PathIcon, SymbolIcon
from search.hits import Failed, Found, Hit
from search.kinds import command, qmd
from search.merge import (
    Called,
    Resting,
    Target,
    Unanswered,
    Unstarted,
    actions,
    decode,
    encode,
    folder,
    interleave,
    problem,
    rows,
    summary,
    tidy,
)
from search.settings import Provider

QMD = Provider("qmd", "qmd", ("n",), qmd.Settings("/q"), reference="Copy docid")
RG = Provider("notes-rg", "command", ("n",), command.Settings("/rg", ("{text}",), "paths"))
HOME = "/Users/bruk"


def _found(*hits: Hit, keys: tuple[str | None, ...] = ()) -> Called:
    return Called(Found(hits), 0, timed_out=False, keys=keys)


def _paths(merged_rows: tuple[object, ...]) -> list[str | None]:
    found = []
    for row in merged_rows:
        target = decode(getattr(row, "id", ""))
        found.append(target.path if target is not None else None)
    return found


# --- 4. rank over score ---------------------------------------------------------------------------


def test_hits_keep_the_order_the_provider_printed_whatever_their_score() -> None:
    # qmd printed a hit scored 0 above one scored 0.49: the order is the rank.
    report = qmd.read(
        qmd.Settings("/q"),
        CallResult(
            0,
            b'[{"file": "/n/zero.md", "score": 0}, {"file": "/n/high.md", "score": 0.49}]',
            b"",
            timed_out=False,
        ),
        Path("/"),
        10,
    )
    merged = rows([(QMD, Called(report, 0, timed_out=False))], 1.0, HOME)
    assert _paths(merged) == ["/n/zero.md", "/n/high.md"]
    assert all(row.score is None for row in merged)


def test_two_providers_interleave_by_rank() -> None:
    answers = [
        (QMD, _found(Hit("a", path="/n/a"), Hit("b", path="/n/b"), Hit("c", path="/n/c"))),
        (RG, _found(Hit("x", path="/n/x"))),
    ]
    assert _paths(rows(answers, 1.0, HOME)) == ["/n/a", "/n/x", "/n/b", "/n/c"]


def test_ties_go_to_config_order() -> None:
    answers = [(RG, _found(Hit("x", path="/n/x"))), (QMD, _found(Hit("a", path="/n/a")))]
    assert _paths(rows(answers, 1.0, HOME)) == ["/n/x", "/n/a"]


# --- 8. merging -------------------------------------------------------------------------------------


def test_the_same_real_path_collapses_and_names_both_providers() -> None:
    answers = [
        (
            QMD,
            _found(
                Hit("Offsite", path="/Users/bruk/Notes/offsite.md", snippet="Budget"),
                keys=("/real/offsite.md",),
            ),
        ),
        (RG, _found(Hit("offsite.md", path="/link/offsite.md"), keys=("/real/offsite.md",))),
    ]
    (row,) = rows(answers, 1.0, HOME)
    assert row.title == "Offsite"
    assert row.subtitle == "qmd, notes-rg: Budget"
    target = decode(row.id)
    assert target is not None
    assert target.by == ("qmd", "notes-rg")
    assert target.path == "/Users/bruk/Notes/offsite.md"


def test_an_unresolved_path_is_compared_as_written() -> None:
    answers = [
        (QMD, _found(Hit("a", path="/n/a"), keys=(None,))),
        (RG, _found(Hit("a", path="/n/a"))),
    ]
    assert len(rows(answers, 1.0, HOME)) == 1


def test_the_same_url_collapses_and_the_reference_comes_from_whichever_has_one() -> None:
    url = "https://example.com/t/1"
    answers = [
        (RG, _found(Hit("Ticket", url=url))),
        (QMD, _found(Hit("Ticket again", url=url, reference="#abc"))),
    ]
    (row,) = rows(answers, 1.0, HOME)
    assert row.title == "Ticket"
    target = decode(row.id)
    assert target is not None
    assert target.reference == "#abc"
    assert target.by == ("notes-rg", "qmd")


def test_hits_with_neither_path_nor_url_never_collapse() -> None:
    answers = [(QMD, _found(Hit("same"))), (RG, _found(Hit("same")))]
    assert len(rows(answers, 1.0, HOME)) == 2


def test_merged_hits_keep_the_best_rank() -> None:
    answers = [
        (QMD, _found(Hit("a", path="/n/a"), Hit("b", path="/n/b"))),
        (RG, _found(Hit("b", path="/n/b"), Hit("c", path="/n/c"))),
    ]
    assert _paths(rows(answers, 1.0, HOME)) == ["/n/a", "/n/b", "/n/c"]
    assert [m.by for m in interleave(answers)] == [("qmd",), ("notes-rg", "qmd"), ("notes-rg",)]


def test_problem_rows_come_after_the_hits_one_per_provider() -> None:
    answers = [
        (QMD, Called(Failed("Collection not found: nosuch"), 1, timed_out=False)),
        (RG, _found(Hit("a", path="/n/a"))),
    ]
    merged = rows(answers, 1.0, HOME)
    assert [row.id for row in merged][1:] == ["problem:qmd"]
    assert merged[1].title == "qmd: Collection not found: nosuch"
    assert merged[1].subtitle == "exit 1; check this provider in config.toml"


def test_the_no_hits_row_names_the_providers_and_a_qmd_index() -> None:
    indexed = Provider("qmd", "qmd", ("n",), qmd.Settings("/q", index="work"), scope="index work")
    (row,) = rows([(indexed, _found()), (RG, _found())], 1.0, HOME)
    assert (row.id, row.title, row.subtitle) == (
        "none",
        "No hits in qmd, notes-rg",
        "qmd searched index work",
    )


# --- the problem table ------------------------------------------------------------------------------


def _problem(report: object) -> tuple[str, str] | None:
    return problem(RG, report, 1.0)  # type: ignore[arg-type]


def test_each_problem_row_of_the_table() -> None:
    assert _problem(
        Called(Failed("/usr/bin/env: 'node': No such file or directory"), 127, timed_out=False)
    ) == (
        "notes-rg: /usr/bin/env: 'node': No such file or directory",
        "a program it needs is not on its PATH: set env.PATH",
    )
    assert _problem(Unstarted("cannot run /rg: No such file or directory")) == (
        "notes-rg: cannot run /rg: No such file or directory",
        "check its program in config.toml",
    )
    late = ("notes-rg did not answer within 1.0 s", "its hits are left out; the others' are above")
    assert _problem(Unanswered()) == late
    assert _problem(Called(Failed("half"), None, timed_out=True)) == late
    assert _problem(Called(Found((), cut=True), None, timed_out=True)) == late
    assert _problem(Called(Found((Hit("a", path="/a"),), cut=True), None, timed_out=True)) == (
        "notes-rg stopped at 1.0 s",
        "its hits above are those it found by then",
    )
    assert _problem(Called(Failed("answer is not qmd's JSON: x"), 0, timed_out=False)) == (
        "notes-rg: answer is not qmd's JSON: x",
        "exit 0",
    )
    assert _problem(Called(Found((Hit("a"),), skipped=3, problem="first"), 0, timed_out=False)) == (
        "notes-rg: 3 entries could not be read",
        "first",
    )
    assert _problem(Resting("14:31", 3)) == (
        "notes-rg is resting after 3 slow answers, until 14:31",
        "its hits are left out",
    )
    failed_with_hits = Found((Hit("a", path="/a"),), failure=Failed("rg: denied"))
    assert _problem(Called(failed_with_hits, 2, timed_out=False)) == (
        "notes-rg: rg: denied",
        "exit 2; check this provider in config.toml",
    )
    assert _problem(_found(Hit("a"))) is None


def test_the_summary_for_the_status_keyword() -> None:
    assert summary(RG, None, 1.0) == "not searched since the plugin started"
    assert summary(RG, _found(Hit("a"), Hit("b")), 1.0) == "last search: 2 hits"
    assert summary(RG, Unanswered(), 1.0) == "last search: notes-rg did not answer within 1.0 s"


# --- the rows and their ids --------------------------------------------------------------------------


def test_a_hit_with_a_path() -> None:
    hit = Hit("Offsite", path="/Users/bruk/Notes/offsite.md", line=3)
    (row,) = rows([(QMD, _found(hit))], 1.0, HOME)
    assert row.subtitle == "qmd: ~/Notes"
    assert row.icon == PathIcon("/Users/bruk/Notes/offsite.md")
    assert [action.title for action in row.actions] == ["Open", "Reveal in Finder", "Copy path"]
    target = decode(row.id)
    assert target is not None
    assert target.open == "file:///Users/bruk/Notes/offsite.md"


def test_a_hit_with_a_path_and_a_reference_offers_the_kinds_copy() -> None:
    (row,) = rows([(QMD, _found(Hit("a", path="/n/a", reference="#1")))], 1.0, HOME)
    assert [action.title for action in row.actions][-1] == "Copy docid"
    (row,) = rows([(RG, _found(Hit("a", path="/n/a", reference="T-1")))], 1.0, HOME)
    assert [action.title for action in row.actions][-1] == "Copy reference"


def test_a_hit_with_a_url() -> None:
    (row,) = rows([(RG, _found(Hit("Ticket", url="https://example.com/t/1")))], 1.0, HOME)
    assert row.subtitle == "notes-rg: https://example.com/t/1"
    assert row.icon == SymbolIcon("link")
    assert [action.title for action in row.actions] == ["Open", "Copy URL"]


def test_a_qmd_hit_not_on_disk() -> None:
    hit = Hit("Hiring plan", url="qmd://notes/hiring-plan.md", reference="#154360")
    (row,) = rows([(QMD, _found(hit))], 1.0, HOME)
    assert row.subtitle == "qmd: not on disk since qmd last indexed it; run qmd update"
    assert row.icon == SymbolIcon("questionmark.folder")
    assert [action.title for action in row.actions] == ["Copy docid", "Copy qmd URI"]


def test_a_hit_with_a_title_alone() -> None:
    (row,) = rows([(RG, _found(Hit("Only", snippet="text")))], 1.0, HOME)
    assert row.subtitle == "notes-rg: text"
    assert row.icon == SymbolIcon("doc.text")
    assert [action.title for action in row.actions] == ["Copy text"]


def test_a_path_that_is_not_utf8_gets_a_row_the_protocol_can_carry() -> None:
    (row,) = rows([(RG, _found(Hit("caf�.md", path="/n/caf\udce9.md")))], 1.0, HOME)
    assert row.icon == SymbolIcon("doc")
    json.dumps(row.id).encode("utf-8")
    target = decode(row.id)
    assert target is not None
    assert target.path == "/n/caf\udce9.md"


def test_ids_never_repeat_even_for_hits_that_never_collapse() -> None:
    answers = [
        (QMD, _found(Hit("same"), Hit("same"))),
        (RG, Called(Failed("x"), 2, timed_out=False)),
    ]
    ids = [row.id for row in rows(answers, 1.0, HOME)]
    assert len(ids) == len(set(ids)) == 3


def test_an_id_round_trips_and_a_foreign_one_is_none() -> None:
    target = Target("t", ("qmd",), 4, path="/a b", open="file:///a%20b", reference="#1")
    assert decode(encode(target)) == target
    assert decode("{not json") is None
    assert decode('{"title": "t"}') is None
    assert decode('{"title": "t", "by": [], "at": 0, "path": 3}') is None


def test_the_first_action_is_the_default_for_every_shape() -> None:
    assert actions(Target("t", (), 0, path="/a"), "Copy docid")[0].id == "open"
    assert (
        actions(Target("t", (), 0, url="qmd://n/a.md", reference="#1"), "x")[0].id
        == "copy-reference"
    )
    assert actions(Target("t", (), 0, url="qmd://n/a.md"), "x")[0].id == "copy-uri"
    assert actions(Target("t", (), 0, url="https://e.com"), "x")[0].id == "open"
    assert actions(Target("t", (), 0), "x")[0].id == "copy-text"


def test_folder_shortens_home() -> None:
    assert folder("/Users/bruk/a.md", HOME) == "~"
    assert folder("/Users/bruk/Notes/a.md", HOME) == "~/Notes"
    assert folder("/Users/brukx/a.md", HOME) == "/Users/brukx"


def test_tidy_shows_control_characters_as_question_marks_and_cuts_long_text() -> None:
    assert tidy("a\x08b\rc\nd\x1b") == "a?b?c?d?"
    assert tidy("é ⌘ fine") == "é ⌘ fine"
    long = tidy("y" * 500)
    assert len(long) == 160
    assert long.endswith("…")
