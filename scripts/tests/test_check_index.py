"""The plugin index: its shape without the network, and its entries against a local git repository."""

import tomllib
from pathlib import Path
from typing import Any

from check_index import git, remote_problems, shape_problems

REPOSITORY = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def entry(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "p",
        "summary": "a plugin",
        "source": "https://x/y",
        "ref": COMMIT,
    }
    return base | fields


def test_a_well_shaped_index_has_no_problems() -> None:
    assert shape_problems({"plugin": [entry(), entry(name="q", subdirectory="plugins/q")]}) == []
    assert shape_problems({"plugin": [entry(ref="v1", commit=COMMIT)]}) == []


def test_each_shape_problem_is_named() -> None:
    assert shape_problems({"plugin": [{"name": "p"}]}) == ["p: missing ref, source, summary"]
    assert shape_problems({"plugin": [entry(colour="red")]}) == ["p: unknown field colour"]
    assert shape_problems({"plugin": [entry(ref=7)]}) == ["p: ref must be a string"]
    assert shape_problems({"plugin": [entry(), entry()]}) == ["p: listed more than once"]
    assert shape_problems({"plugin": [entry(ref="v1")]}) == [
        "p: ref 'v1' is a tag, so `commit` must carry the commit it was reviewed at"
    ]
    assert shape_problems({"plugin": [entry(ref="v1", commit="abc")]}) == [
        "p: commit 'abc' is not a full commit hash"
    ]
    assert shape_problems({"plugin": {"name": "p"}}) == [
        "`plugin` must be an array of tables ([[plugin]])"
    ]


def repository_with_a_plugin(root: Path, name: str) -> tuple[str, str]:
    """A git repository holding plugins/<name>/cmd-plugin.toml, tagged v1; its URL and commit."""
    plugin = root / "plugins" / name
    plugin.mkdir(parents=True)
    plugin.joinpath("cmd-plugin.toml").write_text(
        f'name = "{name}"\ncommand = ["true"]\n', encoding="utf-8"
    )
    git("-C", str(root), "init", "-q", "-b", "main")
    git("-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    git(
        "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "plugin"
    )
    git("-C", str(root), "tag", "v1")
    return root.as_uri(), git("-C", str(root), "rev-parse", "HEAD").strip()


def test_an_entry_is_checked_against_its_repository(tmp_path: Path) -> None:
    source, commit = repository_with_a_plugin(tmp_path / "repo", "p")
    good = entry(source=source, ref=commit, subdirectory="plugins/p")
    assert remote_problems(good) == []
    assert remote_problems(good | {"ref": "v1", "commit": commit}) == []
    assert remote_problems(good | {"name": "q"}) == [f"q: the manifest at {commit!r} is named 'p'"]
    assert remote_problems(good | {"ref": "v1", "commit": COMMIT}) == [
        f"p: tag 'v1' now points at {commit}, not {COMMIT}",
    ]
    [problem] = remote_problems(good | {"subdirectory": "plugins/missing"})
    assert problem.startswith(f"p: cannot read the manifest at {commit!r}")


def test_the_repository_index_is_well_shaped() -> None:
    index = tomllib.loads((REPOSITORY / "plugins" / "index.toml").read_text(encoding="utf-8"))
    assert shape_problems(index) == []
    assert {plugin["name"] for plugin in index["plugin"]} == {"calculator", "websearch"}
