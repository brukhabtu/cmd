import json
import os
from pathlib import Path

import pytest
from watchdemo.keeper import CORRUPT_SUFFIX, STATE_FILE, Store
from watchdemo.state import Change, State, watch


def test_a_new_store_starts_empty_with_no_file(tmp_path: Path) -> None:
    store = Store.load(tmp_path)
    assert store.state == State()
    assert store.recovered is None
    assert not (tmp_path / STATE_FILE).exists()


def test_a_change_is_kept_and_read_back(tmp_path: Path) -> None:
    store = Store.load(tmp_path)
    store.transact(lambda state: (watch(state, "A", "Open"), None))
    again = Store.load(tmp_path)
    assert again.state.watched == {"A"}
    assert again.state.seen == {"A": "Open"}


def test_the_write_is_atomic_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = Store.load(tmp_path)
    store.transact(lambda state: (watch(state, "A", "Open"), None))
    assert sorted(path.name for path in tmp_path.iterdir()) == [STATE_FILE]


def test_the_write_goes_through_a_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    renames: list[tuple[str, str]] = []
    real = os.replace

    def spy(source: Path, target: Path) -> None:
        renames.append((Path(source).name, Path(target).name))
        real(source, target)

    monkeypatch.setattr(os, "replace", spy)
    Store.load(tmp_path).transact(lambda state: (watch(state, "A", None), None))
    assert renames == [(STATE_FILE + ".tmp", STATE_FILE)]


def test_a_failed_rename_leaves_the_old_file_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = Store.load(tmp_path)
    store.transact(lambda state: (watch(state, "A", "Open"), None))
    before = (tmp_path / STATE_FILE).read_text(encoding="utf-8")

    def refuse(_a: object, _b: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    store.transact(lambda state: (watch(state, "B", None), None))
    assert (tmp_path / STATE_FILE).read_text(encoding="utf-8") == before
    assert store.state.watched == {"A", "B"}  # the plugin goes on in memory
    assert "cannot keep" in capsys.readouterr().err


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"version": 1}',
        '{"version": 9, "watched": [], "seen": {}, "recent": []}',
        "",
    ],
)
def test_a_corrupt_file_starts_empty_notes_once_and_is_set_aside(
    tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / STATE_FILE).write_text(content, encoding="utf-8")
    store = Store.load(tmp_path)
    assert store.state == State()
    assert store.recovered is not None
    assert "started with nothing watched" in store.recovered
    assert capsys.readouterr().err.count("started with nothing watched") == 1
    assert (tmp_path / (STATE_FILE + CORRUPT_SUFFIX)).read_text(encoding="utf-8") == content
    store.transact(lambda state: (watch(state, "A", None), None))
    assert Store.load(tmp_path).state.watched == {"A"}
    assert Store.load(tmp_path).recovered is None


def test_an_unreadable_file_starts_empty_with_a_note(tmp_path: Path) -> None:
    (tmp_path / STATE_FILE).mkdir()
    store = Store.load(tmp_path)
    assert store.state == State()
    assert store.recovered is not None
    assert "cannot be read" in store.recovered


def test_no_directory_keeps_the_state_in_memory(tmp_path: Path) -> None:
    store = Store.load(None)
    store.transact(lambda state: (watch(state, "A", None), None))
    assert store.state.watched == {"A"}
    assert list(tmp_path.iterdir()) == []


def test_transact_returns_what_the_change_returns_and_skips_the_write_when_unchanged(
    tmp_path: Path,
) -> None:
    store = Store.load(tmp_path)
    assert store.transact(lambda state: (state, 42)) == 42
    assert not (tmp_path / STATE_FILE).exists()


def test_the_file_is_the_documented_shape(tmp_path: Path) -> None:
    store = Store.load(tmp_path)
    change = Change("A", "t", "x", "y", "2026-10-14T19:00:00")
    store.transact(lambda _state: (State(frozenset({"A"}), {"A": "y"}, (change,)), None))
    assert json.loads((tmp_path / STATE_FILE).read_text(encoding="utf-8")) == {
        "version": 1,
        "watched": ["A"],
        "seen": {"A": "y"},
        "recent": [{"id": "A", "title": "t", "old": "x", "new": "y", "at": "2026-10-14T19:00:00"}],
    }
