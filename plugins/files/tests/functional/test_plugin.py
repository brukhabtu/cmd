"""The shell against fake ``mdfind`` and ``open`` scripts on PATH, so it runs anywhere."""

import os
from dataclasses import dataclass
from pathlib import Path

import files
import pytest
from cmd_sdk import Close, Open, Show
from files import PLUGIN


@dataclass(frozen=True)
class Fakes:
    """The two fake programs, where they log their arguments, and what mdfind answers."""

    mdfind_log: Path
    open_log: Path
    found: tuple[str, ...]

    def mdfind_arguments(self) -> list[str]:
        return self.mdfind_log.read_text().split("\n")[:-1]

    def open_arguments(self) -> list[str]:
        return self.open_log.read_text().split("\n")[:-1]


def _install(bin_dir: Path, name: str, body: str) -> None:
    script = bin_dir / name
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fakes:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mdfind_log = tmp_path / "mdfind.log"
    open_log = tmp_path / "open.log"
    found = (str(tmp_path / "Projects" / "cmd" / "README.md"), str(tmp_path / "readme.txt"))
    _install(
        bin_dir,
        "mdfind",
        f"printf '%s\\n' \"$@\" >> '{mdfind_log}'\nprintf '%s\\0' '{found[0]}' '{found[1]}'",
    )
    _install(bin_dir, "open", f"printf '%s\\n' \"$@\" >> '{open_log}'")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("HOME", str(tmp_path))
    return Fakes(mdfind_log, open_log, found)


def test_the_keyword_alone_offers_a_hint_and_enter_explains(fakes: Fakes) -> None:
    (item,) = PLUGIN.query("  ")
    assert not item.id
    assert isinstance(PLUGIN.run("", "default"), Show)
    assert not fakes.mdfind_log.exists()


def test_a_name_is_searched_with_mdfind_and_rows_carry_the_folder_and_both_actions(
    fakes: Fakes,
) -> None:
    rows = PLUGIN.query("readme")
    assert fakes.mdfind_arguments() == ["-0", "-name", "readme"]
    assert [row.title for row in rows] == ["readme.txt", "README.md"]
    assert [row.subtitle for row in rows] == ["~", "~/Projects/cmd"]
    assert all([action.id for action in row.actions] == ["reveal", "open"] for row in rows)


def test_enter_reveals_in_finder_and_the_second_action_opens_a_file_url(fakes: Fakes) -> None:
    path = fakes.found[0]
    assert PLUGIN.run(path, "default") == Close()
    assert fakes.open_arguments() == ["-R", path]
    assert PLUGIN.run(path, "reveal") == Close()
    assert PLUGIN.run(path, "open") == Open(target=f"file://{path}")
    assert fakes.open_arguments() == ["-R", path, "-R", path]
    assert isinstance(PLUGIN.run(path, "dance"), Show)


def test_a_failed_reveal_is_shown_not_raised(fakes: Fakes, tmp_path: Path) -> None:
    _install(tmp_path / "bin", "open", "echo 'no such file' >&2\nexit 1")
    effect = PLUGIN.run(fakes.found[1], "default")
    assert effect == Show(text=f"could not reveal {fakes.found[1]}: no such file")


def test_a_slow_search_still_answers_with_what_it_found(
    fakes: Fakes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        tmp_path / "bin",
        "mdfind",
        f"printf '%s\\0' '{fakes.found[0]}' '{fakes.found[1]}'\nexec sleep 5",
    )
    monkeypatch.setattr(files, "SEARCH_DEADLINE", 0.2)
    assert [row.id for row in PLUGIN.query("readme")] == [fakes.found[1], fakes.found[0]]


def test_without_mdfind_the_failure_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    with pytest.raises(FileNotFoundError, match="mdfind"):
        PLUGIN.query("x")
