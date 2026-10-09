"""qmd through the whole path: argv, env, the SDK's call, the reader and the rows.

The contract half runs the captures of the real qmd 2.8.3 (``tests/fixtures/qmd``) through
a fake qmd executable that prints them, named as the provider's ``bin``; what it prints is
chosen through the provider's ``env`` table, so the ``/usr/bin/env`` prefix is exercised.
The other half runs a real qmd, only when ``CMD_TEST_QMD`` names one (decision 11's list,
items 1 and 12).
"""

import json
import os
import sys
from pathlib import Path

import pytest
from cmd_sdk import Copy, Open, PathIcon, SymbolIcon, call
from cmd_sdk.protocol import DEFAULT_ACTION
from search.merge import decode
from search.plugin import Search, query, run, start

FIXTURES = Path(__file__).parent.parent / "fixtures" / "qmd"
_FAKE = Path(__file__).with_name("fake_qmd.py")


def _host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str) -> Search:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    (config / "config.toml").write_text("deadline = 1.5\n" + provider, encoding="utf-8")
    monkeypatch.setenv("CMD_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(config))
    return start(cwd=lambda: tmp_path, home=str(tmp_path))


def _fake(tmp_path: Path) -> Path:
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    fake = fakes / "qmd"
    fake.write_text(f"#!{sys.executable}\n" + _FAKE.read_text(encoding="utf-8"), encoding="utf-8")
    fake.chmod(0o755)
    return fake


def _contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out: str = "", err: str = "", code: int = 0
) -> tuple[Search, Path]:
    fake = _fake(tmp_path)
    env = {
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
        "FAKE_QMD_OUT": str(FIXTURES / out) if out else "",
        "FAKE_QMD_ERR": str(FIXTURES / err) if err else "",
        "FAKE_QMD_EXIT": str(code),
    }
    provider = (
        '[[provider]]\nname = "qmd"\nkind = "qmd"\nkeywords = ["n"]\n'
        f'bin = "{fake}"\ncollections = ["notes", "meetings"]\n'
        f"env = {{ {', '.join(f'{key} = {json.dumps(value)}' for key, value in env.items())} }}\n"
    )
    return _host(tmp_path, monkeypatch, provider), fake.parent / "calls.log"


def _calls(log: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


# --- the contract: each capture through the plugin --------------------------------------------------


def test_the_argv_and_the_env_reach_qmd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    search, log = _contract(tmp_path, monkeypatch, out="search-no-hits.json")
    query(search, "n -offsite budget")
    (seen,) = _calls(log)
    assert seen["argv"] == [
        "search", "--json", "--full-path", "-n", "10",
        "-c", "notes", "-c", "meetings", "--", "-offsite budget",
    ]  # fmt: skip
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["PATH"] == "/opt/homebrew/bin:/usr/bin:/bin"
    assert env["FAKE_QMD_OUT"] == str(FIXTURES / "search-no-hits.json")


def test_two_hits_not_on_disk_show_qmds_order_and_enter_copies_the_docid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = _contract(tmp_path, monkeypatch, out="search-two-hits.json")
    rows = query(search, "n offsite")
    assert [row.title for row in rows] == ["Team offsite planning", "Quarterly planning meeting"]
    assert rows[0].subtitle == "qmd: not on disk since qmd last indexed it; run qmd update"
    assert rows[0].icon == SymbolIcon("questionmark.folder")
    assert run(search, rows[0].id, DEFAULT_ACTION) == Copy(text="#75ebe1")
    assert run(search, rows[1].id, "copy-uri") == Copy(text="qmd://meetings/2026-10-01-planning.md")


def test_one_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    search, _ = _contract(tmp_path, monkeypatch, out="search-one-hit.json")
    (row,) = query(search, "n hiring")
    assert row.title == "Hiring plan 2027"


def test_no_hits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    search, _ = _contract(tmp_path, monkeypatch, out="search-no-hits.json")
    (row,) = query(search, "n nothing")
    assert (row.id, row.title) == ("none", "No hits in qmd")


def test_full_paths_are_files_with_their_icons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = _contract(tmp_path, monkeypatch, out="search-two-hits-full-path.json")
    rows = query(search, "n offsite")
    assert [row.title for row in rows] == ["Team offsite planning", "Quarterly planning meeting"]
    assert rows[0].subtitle == (
        "qmd: We want a two day offsite in March. Budget approved by finance. Venue shortlist:"
        " the lake house and the city loft."
    )
    printed = json.loads((FIXTURES / "search-two-hits-full-path.json").read_text(encoding="utf-8"))
    assert rows[0].icon == PathIcon(printed[0]["file"])
    assert [action.title for action in rows[0].actions] == ["Open", "Reveal in Finder", "Copy path"]


def test_a_keyword_and_text_show_the_hits_and_enter_opens_the_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Acceptance criterion 1, from config alone: qmd prints paths under its working
    # directory, which is the plugin's, and Enter opens the first.
    for relative in ("notes/offsite.md", "meetings/2026-10-01-planning.md"):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text("# note\n", encoding="utf-8")
    search, _ = _contract(tmp_path, monkeypatch, out="search-full-path-under-cwd.json")
    rows = query(search, "n offsite")
    targets = [decode(row.id) for row in rows]
    assert [target.path if target else None for target in targets] == [
        str(tmp_path / "notes/offsite.md"),
        str(tmp_path / "meetings/2026-10-01-planning.md"),
    ]
    assert run(search, rows[0].id, DEFAULT_ACTION) == Open(
        target=(tmp_path / "notes/offsite.md").as_uri()
    )


@pytest.mark.parametrize(
    ("capture", "code", "title", "subtitle"),
    [
        (
            "error-collection-not-found.txt",
            1,
            "qmd: Collection not found: nosuchcollection",
            "exit 1; check this provider in config.toml",
        ),
        (
            "error-usage.txt",
            1,
            "qmd: Usage: qmd search [options] <query>",
            "exit 1; check this provider in config.toml",
        ),
        (
            "error-no-node.txt",
            127,
            "qmd: /usr/bin/env: 'node': No such file or directory",
            "a program it needs is not on its PATH: set env.PATH",
        ),
    ],
)
def test_each_stderr_capture_is_a_problem_row(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - the parameters are the table's
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capture: str,
    code: int,
    title: str,
    subtitle: str,
) -> None:
    search, _ = _contract(tmp_path, monkeypatch, err=capture, code=code)
    (row,) = query(search, "n offsite")
    assert (row.id, row.title, row.subtitle) == ("problem:qmd", title, subtitle)


# --- a real qmd, when one is named --------------------------------------------------------------------

REAL = os.environ.get("CMD_TEST_QMD", "")
REAL_PATH = os.environ.get("CMD_TEST_QMD_PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")


@pytest.mark.skipif(
    not REAL,
    reason="CMD_TEST_QMD does not name a qmd binary; set it, and CMD_TEST_QMD_PATH to a PATH"
    " holding the node it was installed with, to run against a real qmd",
)
def test_a_real_qmd_finds_a_note_through_the_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    isolated = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "PATH": REAL_PATH,
    }
    notes = tmp_path / "notes"
    notes.mkdir()
    note = notes / "offsite.md"
    note.write_text(
        "# Offsite budget\n\nThe offsite budget was approved by finance.\n", encoding="utf-8"
    )
    (notes / "other.md").write_text("# Hiring\n\nTwo engineers.\n", encoding="utf-8")
    # qmd runs in the temporary folder, under a HOME and XDG directories of its own: it
    # never sees the real ones, and indexing for BM25 downloads no model.
    monkeypatch.chdir(tmp_path)
    indexed = call(
        ["/usr/bin/env", "-i", *(f"{key}={value}" for key, value in isolated.items()), REAL,
         "collection", "add", str(notes), "--name", "notes"],
        60.0,
        kill_on_timeout=True,
    )  # fmt: skip
    assert indexed.returncode == 0, indexed.stderr.decode()
    env = ", ".join(f"{key} = {json.dumps(value)}" for key, value in isolated.items())
    search = _host(
        tmp_path,
        monkeypatch,
        f'[[provider]]\nname = "qmd"\nkind = "qmd"\nkeywords = ["n"]\nbin = "{REAL}"\n'
        f'collections = ["notes"]\nenv = {{ {env} }}\n',
    )
    rows = query(search, "n offsite budget")
    target = decode(rows[0].id)
    assert target is not None, [(row.title, row.subtitle) for row in rows]
    assert target.path == os.path.realpath(note)
    assert rows[0].title == "Offsite budget"
    assert rows[0].subtitle == "qmd: The offsite budget was approved by finance."
    assert run(search, rows[0].id, DEFAULT_ACTION) == Open(target=Path(target.path).as_uri())
    (row,) = query(search, "n -nothingmatchesthis")
    assert row.title == "No hits in qmd"
