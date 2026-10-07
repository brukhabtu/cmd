from pathlib import Path

from applications.scan import App, scan


def tree(root: Path) -> None:
    """A fake Applications folder: bundles at two depths, a file in disguise, a nested bundle."""
    (root / "Safari.app").mkdir(parents=True)
    (root / "Visual Studio Code.app").mkdir()
    (root / "Utilities" / "Terminal.app").mkdir(parents=True)
    (root / "Notes.app").write_text("not a bundle")
    (root / "Safari.app" / "Contents" / "Helper.app").mkdir(parents=True)
    (root / "Utilities" / "Deeper" / "Buried.app").mkdir(parents=True)


def test_bundles_are_found_two_levels_down_and_sorted_by_name(tmp_path: Path) -> None:
    tree(tmp_path)
    assert scan([tmp_path]) == (
        App("Safari", tmp_path / "Safari.app"),
        App("Terminal", tmp_path / "Utilities" / "Terminal.app"),
        App("Visual Studio Code", tmp_path / "Visual Studio Code.app"),
    )


def test_a_plain_file_named_like_a_bundle_is_not_an_application(tmp_path: Path) -> None:
    tree(tmp_path)
    assert all(app.name != "Notes" for app in scan([tmp_path]))


def test_a_bundle_inside_a_bundle_is_a_helper_and_a_deeper_folder_is_out_of_reach(
    tmp_path: Path,
) -> None:
    tree(tmp_path)
    names = {app.name for app in scan([tmp_path])}
    assert "Helper" not in names
    assert "Buried" not in names
    assert "Buried" in {app.name for app in scan([tmp_path], depth=3)}


def test_a_missing_root_is_skipped_and_the_others_still_answer(tmp_path: Path) -> None:
    tree(tmp_path)
    assert scan([tmp_path / "nowhere", tmp_path]) == scan([tmp_path])
    assert scan([tmp_path / "nowhere"]) == ()


def test_the_same_bundle_reached_twice_is_listed_once(tmp_path: Path) -> None:
    tree(tmp_path)
    assert scan([tmp_path, tmp_path]) == scan([tmp_path])


def test_names_sort_without_regard_to_case(tmp_path: Path) -> None:
    (tmp_path / "zed.app").mkdir()
    (tmp_path / "Xcode.app").mkdir()
    (tmp_path / "activity.app").mkdir()
    assert [app.name for app in scan([tmp_path])] == ["activity", "Xcode", "zed"]
