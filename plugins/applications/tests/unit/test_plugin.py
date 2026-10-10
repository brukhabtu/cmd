from pathlib import Path

import pytest
from applications import DEFAULT_ROOTS, LIMIT, PLUGIN, plugin_for, roots_from_args
from cmd_sdk import Open, PathIcon, Show


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "Safari.app").mkdir()
    (tmp_path / "Visual Studio Code.app").mkdir()
    (tmp_path / "Utilities" / "Terminal.app").mkdir(parents=True)
    (tmp_path / "Notes.app").write_text("not a bundle")
    return tmp_path


def test_part_of_a_name_is_one_row_with_the_bundle_its_folder_and_its_icon(root: Path) -> None:
    (item,) = plugin_for([root]).query("saf")
    assert item.id == str(root / "Safari.app")
    assert item.title == "Safari"
    assert item.subtitle == str(root)
    assert item.score is not None
    assert 0.0 < item.score <= 1.0
    assert item.icon == PathIcon(str(root / "Safari.app"))


def test_rows_come_best_first_and_a_bundle_one_folder_down_is_found(root: Path) -> None:
    rows = plugin_for([root]).query("t")
    assert [row.title for row in rows] == ["Terminal", "Visual Studio Code"]
    assert rows[0].subtitle == str(root / "Utilities")
    scores = [row.score for row in rows]
    assert scores == sorted(scores, key=lambda found: -(found or 0.0))


def test_a_plain_file_and_an_unmatched_name_are_not_rows(root: Path) -> None:
    assert all(row.title != "Notes" for row in plugin_for([root]).query("n"))
    assert plugin_for([root]).query("zzzz") == ()
    assert plugin_for([root]).query("  ") == ()


def test_no_more_than_the_limit_is_shown(tmp_path: Path) -> None:
    for index in range(LIMIT + 3):
        (tmp_path / f"Tool {index:02}.app").mkdir()
    assert len(plugin_for([tmp_path]).query("tool")) == LIMIT


def test_enter_opens_the_bundle_as_a_file_url(root: Path) -> None:
    bundle = str(root / "Visual Studio Code.app")
    expected = Open(target=f"file://{root}/Visual%20Studio%20Code.app")
    assert plugin_for([root]).run(bundle, "default") == expected
    assert plugin_for([root]).run(bundle, "open") == expected


def test_a_bundle_that_has_gone_and_an_unknown_action_are_shown_not_opened(root: Path) -> None:
    gone = str(root / "Gone.app")
    assert plugin_for([root]).run(gone, "default") == Show(text=f"{gone} is no longer there")
    assert isinstance(plugin_for([root]).run(str(root / "Safari.app"), "dance"), Show)


def test_the_default_plugin_has_no_keyword_and_scans_the_three_places_apps_live() -> None:
    assert PLUGIN.description.name == "applications"
    assert PLUGIN.description.keyword is None
    assert DEFAULT_ROOTS[0] == Path("/Applications")
    assert DEFAULT_ROOTS[-1] == Path("/System/Applications")
    assert all(root.name == "Applications" for root in DEFAULT_ROOTS)


def test_roots_come_from_repeated_root_flags_or_are_the_defaults() -> None:
    assert roots_from_args([]) == DEFAULT_ROOTS
    assert roots_from_args(["--root", "/a", "--root", "/b c"]) == (Path("/a"), Path("/b c"))
    with pytest.raises(ValueError, match="--verbose"):
        roots_from_args(["--root", "/a", "--verbose"])
    with pytest.raises(ValueError, match="--root"):
        roots_from_args(["--root"])


def test_a_second_query_does_not_walk_the_roots_again(root: Path) -> None:
    plugin = plugin_for([root])
    assert [row.title for row in plugin.query("saf")] == ["Safari"]
    (root / "Safari2.app").mkdir()
    assert [row.title for row in plugin.query("saf")] == ["Safari"]


def test_a_warm_plugin_answers_a_query_made_while_it_scans(root: Path) -> None:
    plugin = plugin_for([root], warm=True)
    assert [row.title for row in plugin.query("saf")] == ["Safari"]
