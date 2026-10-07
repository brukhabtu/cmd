from pathlib import Path

import pytest
from cmd_sdk import PathIcon
from files.search import (
    LIMIT,
    file_url,
    parent_folder,
    paths_from,
    rank,
    reveal_arguments,
    score,
    search_arguments,
)

HOME = Path("/Users/me")


def test_mdfind_is_asked_for_nul_separated_paths_matching_the_name() -> None:
    assert search_arguments("  readme ") == ("-0", "-name", "readme")


@pytest.mark.parametrize(
    ("output", "paths"),
    [
        (b"", ()),
        (b"/a/x.txt\0/b/y.txt\0", ("/a/x.txt", "/b/y.txt")),
        (b"/a/x.txt\0\0/b/y.txt", ("/a/x.txt", "/b/y.txt")),
        (b"/a/caf\xc3\xa9.txt\0", ("/a/café.txt",)),
        (b"/a/bad\xff.txt\0", ("/a/bad�.txt",)),
    ],
)
def test_paths_are_split_on_nul_and_empties_dropped(output: bytes, paths: tuple[str, ...]) -> None:
    assert paths_from(output) == paths


@pytest.mark.parametrize(
    ("path", "folder"),
    [
        ("/Users/me/Documents/notes.md", "~/Documents"),
        ("/Users/me/notes.md", "~"),
        ("/Users/me/a b/c.txt", "~/a b"),
        ("/Applications/Safari.app", "/Applications"),
        ("/Users/meagain/x.txt", "/Users/meagain"),
    ],
)
def test_the_parent_folder_shortens_home_to_a_tilde(path: str, folder: str) -> None:
    assert parent_folder(path, HOME) == folder


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("readme", "readme", 1.0),
        ("README", "readme", 1.0),
        ("readme.md", "readme", 0.8),
        ("my-readme.md", "readme", 0.6),
        ("notes.md", "readme", 0.4),
    ],
)
def test_a_name_scores_by_how_closely_it_matches(name: str, text: str, expected: float) -> None:
    assert score(name, text) == expected


def test_rows_are_best_match_first_then_shallow_then_by_name() -> None:
    paths = (
        "/Users/me/Projects/deep/tree/readme.md",
        "/Users/me/notes.md",
        "/Users/me/Projects/readme.md",
        "/Users/me/Projects/b-readme.txt",
        "/Users/me/Projects/a-readme.txt",
        "/Users/me/readme",
    )
    rows = rank(paths, "readme", HOME)
    assert [row.id for row in rows] == [
        "/Users/me/readme",
        "/Users/me/Projects/readme.md",
        "/Users/me/Projects/deep/tree/readme.md",
        "/Users/me/Projects/a-readme.txt",
        "/Users/me/Projects/b-readme.txt",
        "/Users/me/notes.md",
    ]
    assert [row.score for row in rows] == [1.0, 0.8, 0.8, 0.6, 0.6, 0.4]


def test_a_row_carries_the_name_the_folder_and_reveal_then_open() -> None:
    (row,) = rank(("/Users/me/Documents/readme.md",), "readme", HOME)
    assert row.title == "readme.md"
    assert row.subtitle == "~/Documents"
    assert [action.id for action in row.actions] == ["reveal", "open"]
    assert row.actions[0].title == "Reveal in Finder"
    assert row.icon == PathIcon("/Users/me/Documents/readme.md")


def test_no_more_than_the_limit_is_shown() -> None:
    paths = tuple(f"/Users/me/readme-{index:03}.md" for index in range(LIMIT + 5))
    assert len(rank(paths, "readme", HOME)) == LIMIT


def test_a_file_url_has_a_scheme_and_is_percent_encoded() -> None:
    assert file_url("/a b/c.txt") == "file:///a%20b/c.txt"
    assert file_url("/Users/me/x.md") == "file:///Users/me/x.md"


def test_reveal_asks_open_to_select_the_file_in_finder() -> None:
    assert reveal_arguments("/a/b.txt") == ("-R", "/a/b.txt")
