"""The plugin against a fake provider executable, with the host's directories and the clock
faked at the boundary (decision 11's list, items 7, 9, 10 and 11).

The fake is ``fake_provider.py``, copied into a temporary directory and named in a
``command`` provider, as a real tool would be. It logs every start, so a test can tell a
search that started a process from one that did not. Calls go through the SDK's real
``call``; only the clock the cache and the rest age by is injected.
"""

import io
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cmd_sdk import Close, Copy, Item, Open, Show, serve
from cmd_sdk.protocol import DEFAULT_ACTION
from search import plugin as shell
from search.kinds import command
from search.merge import decode
from search.plugin import Search, plugin, query, run, start

_FAKE = Path(__file__).with_name("fake_provider.py")

HOST_QUERY_TIMEOUT = 3.0
"""The host's query timeout (docs/plugin-protocol.md)."""


@dataclass
class Clock:
    """The time the plugin sees, moved by the test."""

    now: datetime = field(default_factory=lambda: datetime(2026, 10, 9, 14, 1).astimezone())

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)

    def ticks(self) -> float:
        return self.now.timestamp()


@dataclass
class Host:
    """The directories the host gives the plugin, the fake provider and a folder of notes."""

    tmp: Path
    data: Path
    config: Path
    fake: Path
    notes: Path
    clock: Clock = field(default_factory=Clock)
    opener: Path | None = None

    def configure(self, text: str) -> None:
        self.config.mkdir(parents=True, exist_ok=True)
        (self.config / "config.toml").write_text(text, encoding="utf-8")

    def start(self) -> Search:
        return start(
            clock=self.clock,
            ticks=self.clock.ticks,
            cwd=lambda: self.tmp,
            home=str(self.tmp),
            opener=str(self.opener) if self.opener else shell.OPENER,
        )

    def starts(self) -> list[list[str]]:
        log = self.fake.parent / "starts.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def note(self, name: str) -> str:
        path = self.notes / name
        path.write_text(f"# {name}\n", encoding="utf-8")
        return str(path)


def provider(  # ruff: ignore[too-many-arguments] - a provider's table, one key each
    name: str,
    keywords: list[str],
    fake: Path,
    mode: str,
    *items: str,
    form: str = "paths",
    exit_codes: list[int] | None = None,
    extra: str = "",
) -> str:
    """A ``[[provider]]`` table of the command kind running the fake in ``mode``."""
    argv = [str(fake), mode, *items, "--", "{text}"]
    lines = [
        "[[provider]]",
        f'name = "{name}"',
        'kind = "command"',
        f"keywords = {json.dumps(keywords)}",
        f"command = {json.dumps(argv)}",
        f'format = "{form}"',
    ]
    if exit_codes is not None:
        lines.append(f"exit_codes = {json.dumps(exit_codes)}")
    return "\n".join(lines) + "\n" + extra + "\n"


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Host:
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    fake = fakes / "provider"
    fake.write_text(f"#!{sys.executable}\n" + _FAKE.read_text(encoding="utf-8"), encoding="utf-8")
    fake.chmod(0o755)
    data = tmp_path / "data"
    data.mkdir()
    notes = tmp_path / "notes"
    notes.mkdir()
    monkeypatch.setenv("CMD_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(tmp_path / "config"))
    return Host(tmp_path, data, tmp_path / "config", fake, notes)


def _timed(search: Search, text: str) -> tuple[tuple[Item, ...], float]:
    began = time.monotonic()
    rows = query(search, text)
    return rows, time.monotonic() - began


def _paths(rows: tuple[Item, ...]) -> list[str]:
    paths = []
    for row in rows:
        target = decode(row.id)
        if target is not None and target.path is not None:
            paths.append(target.path)
    return paths


def _problems(rows: tuple[Item, ...]) -> list[tuple[str, str | None]]:
    return [(row.title, row.subtitle) for row in rows if row.id.startswith("problem:")]


# --- keywords that cost nothing -------------------------------------------------------------------


def test_a_first_word_that_is_no_keyword_starts_nothing(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "paths", host.note("a.md")))
    search = host.start()
    assert query(search, "hello world") == ()
    assert query(search, "nn offsite") == ()
    assert query(search, "") == ()
    assert host.starts() == []


def test_text_shorter_than_min_chars_starts_nothing(host: Host) -> None:
    host.configure(
        "min_chars = 3\n"
        + provider("qmd", ["n"], host.fake, "empty")
        + provider("rg", ["n"], host.fake, "empty")
    )
    search = host.start()
    (row,) = query(search, "n ab")
    assert (row.id, row.title, row.subtitle) == (
        "hint:min",
        "Search qmd, rg",
        "Type at least 3 characters after n",
    )
    assert query(search, "N")[0].id == "hint:min"
    assert host.starts() == []
    assert run(search, row.id, DEFAULT_ACTION) == Show(text="Type a few more characters to search")


# --- AC2: two providers searched together and merged ---------------------------------------------


def test_two_providers_on_one_keyword_are_searched_together_and_merged_by_rank(host: Host) -> None:
    a, b, c, d = (host.note(name) for name in ("a.md", "b.md", "c.md", "d.md"))
    host.configure(
        provider("qmd", ["n", "qmd"], host.fake, "paths", a, b)
        + provider("rg", ["n", "grep"], host.fake, "nul", c, d)
    )
    search = host.start()
    rows = query(search, "n offsite")
    assert _paths(rows) == [a, c, b, d]
    assert [row.subtitle for row in rows] == [
        "qmd: ~/notes",
        "rg: ~/notes",
        "qmd: ~/notes",
        "rg: ~/notes",
    ]
    assert len(host.starts()) == 2
    assert _paths(query(search, "grep offsite")) == [c, d]


def test_the_same_file_from_two_providers_collapses_through_a_symlink(host: Host) -> None:
    real = host.note("offsite.md")
    (host.tmp / "linked").symlink_to(host.notes)
    host.configure(
        provider("qmd", ["n"], host.fake, "paths", real)
        + provider("rg", ["n"], host.fake, "paths", str(host.tmp / "linked" / "offsite.md"))
    )
    (row,) = query(host.start(), "n offsite")
    assert row.subtitle == "qmd, rg: ~/notes"
    target = decode(row.id)
    assert target is not None
    assert (target.path, target.by) == (real, ("qmd", "rg"))


# --- every failure mode beside a working provider -----------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "extra", "expected"),
    [
        (
            "fail",
            [],
            (
                "broken: rg: /nowhere: No such file or directory (os error 2)",
                "exit 2; check this provider in config.toml",
            ),
        ),
        (
            "slow",
            [],
            ("broken did not answer within 0.5 s", "its hits are left out; the others' are above"),
        ),
        (
            "partial",
            ["/p/kept.md"],
            ("broken stopped at 0.5 s", "its hits above are those it found by then"),
        ),
        (
            "garbage",
            [],
            (
                "broken: 2 entries are not paths: '\ufffd\ufffd not a path {{{ nor JSON' is not an absolute path",
                "exit 0",
            ),
        ),
        (
            "exit2-hits",
            ["/p/kept.md"],
            (
                "broken: rg: /locked: Permission denied (os error 13)",
                "exit 2; check this provider in config.toml",
            ),
        ),
        ("exit1", [], ("broken: exited with 1", "exit 1; check this provider in config.toml")),
        ("grandchild", ["/p/kept.md"], None),
        ("empty", [], None),
    ],
)
def test_a_failing_or_slow_provider_shows_its_message_beside_the_others_hits(
    host: Host, mode: str, extra: list[str], expected: tuple[str, str] | None
) -> None:
    good = host.note("good.md")
    host.configure(
        "deadline = 0.5\n"
        + provider("good", ["n"], host.fake, "paths", good)
        + provider("broken", ["n"], host.fake, mode, *extra)
    )
    rows, took = _timed(host.start(), "n offsite")
    assert took < 0.5 + shell.GRACE + 0.3
    assert _paths(rows)[0] == good
    assert _paths(rows)[1:] == extra
    assert _problems(rows) == ([expected] if expected else [])
    assert [row.id for row in rows][len(extra) + 1 :] == (["problem:broken"] if expected else [])


def test_output_past_the_cap_is_cut_and_the_provider_killed_and_named(host: Host) -> None:
    good = host.note("good.md")
    host.configure(
        provider("flood", ["n"], host.fake, "flood", good)
        + provider("good", ["n"], host.fake, "paths", good)
    )
    rows, took = _timed(host.start(), "n offsite")
    assert took < 2.5
    assert _paths(rows)[0] == good
    assert _problems(rows) == [
        ("flood printed more than the plugin reads", "its hits above are the first it printed")
    ]


def test_a_text_with_a_nul_character_is_a_row_and_starts_nothing(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "paths"))
    (row,) = query(host.start(), "n off\0site")
    assert (row.id, row.title) == ("hint:text", "search: the text has a NUL character")
    assert host.starts() == []


def test_control_characters_and_walls_of_text_never_reach_a_row_raw(host: Host) -> None:
    host.configure(provider("loud", ["n"], host.fake, "noisy"))
    rows = query(host.start(), "n offsite")
    (title, subtitle) = _problems(rows)[0]
    for text in (title, subtitle or ""):
        assert text.isprintable()
        assert len(text) <= 160
    assert title.startswith("loud: boom ?[31mred?[0m ?")


def test_an_exit_code_in_exit_codes_is_an_answer(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "exit1", exit_codes=[0, 1]))
    (row,) = query(host.start(), "n offsite")
    assert (row.id, row.title) == ("none", "No hits in rg")


def test_a_program_gone_since_start_is_a_row(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "paths"))
    search = host.start()
    host.fake.unlink()
    (row,) = query(search, "n offsite")
    assert row.title == f"rg: cannot run {host.fake}: No such file or directory"
    assert row.subtitle == "check its program in config.toml"


def test_several_slow_providers_still_answer_inside_the_hosts_timeout(host: Host) -> None:
    good = host.note("good.md")
    host.configure(
        "deadline = 1.5\n"
        + provider("good", ["n"], host.fake, "paths", good)
        + "".join(provider(f"slow{n}", ["n"], host.fake, "slow") for n in range(3))
        + provider("partial", ["n"], host.fake, "partial", "/p/kept.md")
        + provider("grandchild", ["n"], host.fake, "grandchild", "/p/child.md")
        + provider("late", ["n"], host.fake, "late-grandchild", "1.2", "/p/late.md")
    )
    rows, took = _timed(host.start(), "n offsite")
    # The late provider exits at 1.2 s and its grandchild holds the pipes for call's whole
    # 1 s grace: query waits for it, deadline + grace at most, inside the host's 3 s.
    assert took > 2.0
    assert took < 1.5 + shell.GRACE + 0.2
    assert took < HOST_QUERY_TIMEOUT
    assert set(_paths(rows)) == {good, "/p/kept.md", "/p/child.md", "/p/late.md"}
    assert [title for title, _ in _problems(rows)] == [
        "slow0 did not answer within 1.5 s",
        "slow1 did not answer within 1.5 s",
        "slow2 did not answer within 1.5 s",
        "partial stopped at 1.5 s",
    ]


# --- the cache and the rest -------------------------------------------------------------------------------


def test_a_repeated_text_inside_ten_seconds_starts_nothing(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "paths", host.note("a.md")))
    search = host.start()
    first = query(search, "n offsite")
    assert query(search, "n offsite") == first
    assert len(host.starts()) == 1
    query(search, "n offsit")
    assert len(host.starts()) == 2
    host.clock.advance(10)
    query(search, "n offsite")
    assert len(host.starts()) == 3


def test_a_failure_in_time_is_cached_and_a_timeout_is_not(host: Host) -> None:
    host.configure(
        "deadline = 0.5\n"
        + provider("broken", ["n"], host.fake, "fail")
        + provider("slow", ["s"], host.fake, "slow")
    )
    search = host.start()
    query(search, "n offsite")
    query(search, "n offsite")
    query(search, "s offsite")
    query(search, "s offsite")
    assert [start[0] for start in host.starts()] == ["fail", "slow", "slow"]


def test_three_timeouts_rest_a_provider_and_it_comes_back_after_30_s(host: Host) -> None:
    good = host.note("good.md")
    host.configure(
        "deadline = 0.5\n"
        + provider("good", ["n"], host.fake, "paths", good)
        + provider("slow", ["n"], host.fake, "slow")
    )
    search = host.start()
    for text in ("n one", "n two", "n three"):
        query(search, text)
    slow_starts = len([s for s in host.starts() if s[0] == "slow"])
    assert slow_starts == 3
    rows, took = _timed(search, "n four")
    assert took < 0.5
    assert _paths(rows) == [good]
    assert _problems(rows) == [
        ("slow is resting after 3 slow answers, until 14:01", "its hits are left out")
    ]
    assert len([s for s in host.starts() if s[0] == "slow"]) == 3
    host.clock.advance(30)
    query(search, "n five")
    assert len([s for s in host.starts() if s[0] == "slow"]) == 4


def test_a_call_back_in_time_sets_the_count_back(host: Host) -> None:
    host.configure("deadline = 0.5\n" + provider("flaky", ["n"], host.fake, "slow"))
    search = host.start()
    query(search, "n one")
    query(search, "n two")
    # The tool recovers: the same provider now answers in time.
    host.fake.write_text(
        f"#!{sys.executable}\n"
        + _FAKE.read_text(encoding="utf-8").replace(
            'case "slow":\n            time.sleep(_SLEEP)', 'case "slow":\n            pass'
        ),
        encoding="utf-8",
    )
    query(search, "n three")
    host.fake.write_text(
        f"#!{sys.executable}\n" + _FAKE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    query(search, "n four")
    query(search, "n five")
    rows = query(search, "n six")
    assert _problems(rows) == [
        ("flaky did not answer within 0.5 s", "its hits are left out; the others' are above")
    ]
    assert len(host.starts()) == 6


# --- query never raises -----------------------------------------------------------------------------------


def test_query_never_raises_when_routing_raises(
    host: Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    host.configure(provider("rg", ["n"], host.fake, "paths"))
    search = host.start()

    def boom(*_: object) -> None:
        raise RuntimeError("routing broke")

    monkeypatch.setattr(shell, "route", boom)
    (row,) = query(search, "n offsite")
    assert row.title == "search: RuntimeError: routing broke"


def test_a_kind_that_raises_is_its_providers_problem(
    host: Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = host.note("good.md")
    host.configure(
        provider("good", ["n"], host.fake, "paths", good, form="hits")
        + provider("rg", ["n"], host.fake, "paths", good)
    )
    search = host.start()
    real = command.read

    def read(settings: command.Settings, *rest: object) -> object:
        if settings.format == "paths":
            raise ValueError("the kind broke")
        return real(settings, *rest)  # type: ignore[arg-type]

    monkeypatch.setattr(command, "read", read)
    rows = query(search, "n offsite")
    assert ("rg: ValueError: the kind broke", "exit 0") in _problems(rows)


def test_a_runner_that_raises_is_its_providers_problem(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "paths"))
    search = host.start()

    def runner(*_: object) -> object:
        raise RuntimeError("the call broke")

    broken = Search(search.startup, search.memory, runner, search.clock, search.cwd, search.home)  # type: ignore[arg-type]
    (row,) = query(broken, "n offsite")
    assert row.title == "rg: RuntimeError: the call broke"


def test_row_ids_never_repeat_and_problems_come_after_the_hits(host: Host) -> None:
    a, b = host.note("a.md"), host.note("b.md")
    host.configure(
        "deadline = 0.5\n"
        + provider("one", ["n"], host.fake, "paths", a, b, a)
        + provider("two", ["n"], host.fake, "fail")
        + provider(
            "three",
            ["n"],
            host.fake,
            "lines",
            '{"title": "same"}',
            '{"title": "same"}',
            form="hits",
        )
        + provider("four", ["n"], host.tmp / "missing", "paths")
    )
    rows = query(host.start(), "n offsite")
    ids = [row.id for row in rows]
    assert len(ids) == len(set(ids))
    kinds = ["hit" if row.id.startswith("{") else row.id.split(":")[0] for row in rows]
    assert kinds == ["hit", "hit", "hit", "hit", "problem", "config"]


# --- every config problem as its row -------------------------------------------------------------------------


def test_no_config_shows_where_to_create_it_and_enter_opens_the_directory(host: Host) -> None:
    search = host.start()
    rows = query(search, "search")
    assert rows[1].title == f"No config: create config.toml in {host.config}"
    assert run(search, rows[1].id, DEFAULT_ACTION) == Open(target=host.config.as_uri())
    assert host.config.is_dir()
    assert query(search, "n offsite") == ()


def test_an_empty_config_is_no_config(host: Host) -> None:
    host.configure("")
    assert query(host.start(), "search")[1].title.startswith("No config")


def test_an_unparseable_config_shows_on_the_last_configs_keywords(host: Host) -> None:
    host.configure(provider("rg", ["n", "grep"], host.fake, "paths"))
    host.start()
    host.configure("[[provider]\nname = ")
    search = host.start()
    for text in ("n offsite", "grep x", "search"):
        rows = query(search, text)
        assert any(
            "is not valid TOML" in row.title and "nothing is searched" in row.title for row in rows
        )
    assert host.starts() == []


def test_an_invalid_provider_beside_a_valid_one(host: Host) -> None:
    good = host.note("good.md")
    host.configure(
        provider("good", ["n"], host.fake, "paths", good)
        + '[[provider]]\nname = "bad"\nkind = "qmd"\nkeywords = ["n", "bad"]\nbin = "/q"\nmode = "query"\n'
    )
    search = host.start()
    rows = query(search, "n offsite")
    assert _paths(rows) == [good]
    assert rows[-1].id == "config:0"
    assert rows[-1].title.startswith('bad: mode: "query" loads language models')
    assert [row.id for row in query(search, "bad x")] == ["config:0"]


def test_a_program_that_is_not_executable_is_its_providers_only_row(host: Host) -> None:
    plain = host.tmp / "not-executable"
    plain.write_text("", encoding="utf-8")
    good = host.note("good.md")
    host.configure(
        provider("good", ["n"], host.fake, "paths", good)
        + f'[[provider]]\nname = "qmd"\nkind = "qmd"\nkeywords = ["n", "q"]\nbin = "{plain}"\n'
    )
    search = host.start()
    (row,) = query(search, "q offsite")
    assert row.title == f"qmd: {plain} is not an executable file"
    rows = query(search, "n offsite")
    assert _paths(rows) == [good]
    assert rows[-1].title == f"qmd: {plain} is not an executable file"
    assert all(start[0] == "paths" for start in host.starts())


def test_a_config_with_every_kind_of_mistake_gives_rows_and_never_raises(host: Host) -> None:
    host.configure(
        'status_keyword = "two words"\ndeadline = 9\nmin_chars = "two"\nextra = 1\n'
        '[[provider]]\nkind = "qmd"\n'
        '[[provider]]\nname = "a"\nkind = "nope"\nkeywords = ["a"]\n'
        '[[provider]]\nname = "b"\nkind = "qmd"\nkeywords = []\nbin = "/q"\n'
        '[[provider]]\nname = "c"\nkind = "qmd"\nkeywords = ["c"]\nbin = "q"\n'
        '[[provider]]\nname = "d"\nkind = "command"\nkeywords = ["d"]\ncommand = ["/x"]\nformat = "paths"\n'
        '[[provider]]\nname = "e"\nkind = "command"\nkeywords = ["e"]\ncommand = ["/x", "{text}"]\nformat = "paths"\nexit_codes = ["0"]\n'
        '[[provider]]\nname = "f"\nkind = "qmd"\nkeywords = ["search"]\nbin = "/q"\n'
        '[[provider]]\nname = "g"\nkind = "qmd"\nkeywords = ["g"]\nbin = "/q"\nenv = { "bad name" = "x" }\n'
        '[[provider]]\nname = "h"\nkind = "qmd"\nkeywords = ["h"]\nbin = "/q"\nopen = "{line}"\n'
        '[[provider]]\nname = "i"\nkind = "qmd"\nkeywords = ["i"]\nbin = "/no/such/qmd"\ntypo = 1\n'
        '[[provider]]\nname = "j"\nkind = "qmd"\nkeywords = ["j"]\nbin = "/no/such/qmd"\n'
    )
    search = host.start()
    rows = query(search, "search")
    titles = [row.title for row in rows]
    assert len([row for row in rows if row.id.startswith("config:")]) == 15
    assert "j: /no/such/qmd is not an executable file" in titles
    for word in ("a", "c", "d", "e", "g", "h", "i", "j"):
        found = query(search, f"{word} offsite")
        assert found
        assert all(row.id.startswith("config:") for row in found)
    assert host.starts() == []


def test_the_status_keyword_shows_each_provider_and_its_last_outcome(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "fail"))
    search = host.start()
    assert query(search, "search")[1].subtitle == "not searched since the plugin started"
    query(search, "n offsite")
    rows = query(search, "Search")
    assert rows[1].title == "rg: command on n"
    assert (
        rows[1].subtitle == "last search: rg: rg: /nowhere: No such file or directory (os error 2)"
    )


# --- the command kind through the whole path ----------------------------------------------------------------


def test_text_and_limit_reach_the_program_as_arguments(host: Host) -> None:
    host.configure(
        '[[provider]]\nname = "rg"\nkind = "command"\nkeywords = ["n"]\nlimit = 7\nformat = "paths"\n'
        f'command = ["{host.fake}", "echo", "--max-count", "{{limit}}", "*.{{md,txt}}", "--", "{{text}}"]\n'
    )
    query(host.start(), "n -offsite budget")
    assert host.starts() == [["echo", "--max-count", "7", "*.{md,txt}", "--", "-offsite budget"]]


def test_hits_as_json_lines_with_urls_and_titles(host: Host) -> None:
    host.configure(
        provider(
            "tickets", ["t"], host.fake, "lines",
            '{"title": "Ticket", "url": "https://example.com/t/1", "reference": "T-1"}',
            '{"title": "A thought", "snippet": "no file at all"}',
            "not json",
            form="hits",
        )
    )  # fmt: skip
    search = host.start()
    rows = query(search, "t budget")
    assert [row.title for row in rows] == [
        "Ticket",
        "A thought",
        "tickets: 1 entries could not be read",
    ]
    assert run(search, rows[0].id, DEFAULT_ACTION) == Open(target="https://example.com/t/1")
    assert run(search, rows[0].id, "copy-url") == Copy(text="https://example.com/t/1")
    assert run(search, rows[1].id, DEFAULT_ACTION) == Copy(text="A thought")


# --- run ---------------------------------------------------------------------------------------------------


@pytest.fixture
def opener(host: Host) -> Path:
    script = host.tmp / "fakes" / "open"
    log = host.tmp / "fakes" / "open.log"
    script.write_text(
        f"#!{sys.executable}\nimport sys, json\nopen({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    host.opener = script
    return log


def test_each_action_on_a_hit_with_a_path(host: Host, opener: Path) -> None:
    odd = host.note("a b#c%d.md")
    host.configure(
        provider("rg", ["n"], host.fake, "paths", odd)
        + provider(
            "vault", ["o"], host.fake, "paths", odd, extra='open = "obsidian://open?path={path}"'
        )
    )
    search = host.start()
    (row,) = query(search, "n offsite")
    assert [action.id for action in row.actions] == ["open", "reveal", "copy-path"]
    encoded = odd.replace(" ", "%20").replace("#", "%23").replace("%d", "%25d")
    assert run(search, row.id, DEFAULT_ACTION) == Open(target=f"file://{encoded}")
    assert run(search, row.id, "open") == Open(target=f"file://{encoded}")
    assert run(search, row.id, "copy-path") == Copy(text=odd)
    assert run(search, row.id, "reveal") == Close()
    assert json.loads(opener.read_text(encoding="utf-8")) == ["-R", odd]
    assert run(search, row.id, "copy-reference") == Show(
        text="search has no action 'copy-reference' for this row"
    )
    (row,) = query(search, "o offsite")
    assert run(search, row.id, DEFAULT_ACTION) == Open(target=f"obsidian://open?path={encoded}")


def test_ids_are_decoded_with_no_state(host: Host) -> None:
    a = host.note("a.md")
    host.configure(provider("rg", ["n"], host.fake, "paths", a))
    (row,) = query(host.start(), "n offsite")
    fresh = host.start()
    assert run(fresh, row.id, DEFAULT_ACTION) == Open(target=Path(a).as_uri())


def test_a_path_gone_since_the_search_says_so(host: Host) -> None:
    a = host.note("a.md")
    host.configure(provider("rg", ["n"], host.fake, "paths", a))
    search = host.start()
    (row,) = query(search, "n offsite")
    Path(a).unlink()
    assert run(search, row.id, DEFAULT_ACTION) == Show(text=f"{a} is not there any more")
    assert run(search, row.id, "reveal") == Show(text=f"{a} is not there any more")


def test_reveal_without_open_says_so(host: Host) -> None:
    a = host.note("a.md")
    host.configure(provider("rg", ["n"], host.fake, "paths", a))
    host.opener = host.tmp / "no-open"
    search = host.start()
    (row,) = query(search, "n offsite")
    assert run(search, row.id, "reveal") == Show(
        text=f"could not reveal {a}: No such file or directory"
    )


def test_enter_on_a_problem_shows_the_command_and_stderr(host: Host) -> None:
    host.configure(provider("rg", ["n"], host.fake, "fail"))
    search = host.start()
    rows = query(search, "n offsite")
    effect = run(search, rows[0].id, DEFAULT_ACTION)
    assert effect == Show(
        text=f"{host.fake} fail -- offsite\nrg: /nowhere: No such file or directory (os error 2)\nmore detail"
    )
    assert run(host.start(), rows[0].id, DEFAULT_ACTION) == Show(
        text="rg has not been searched since the plugin started"
    )


def test_an_id_this_plugin_did_not_make(host: Host) -> None:
    search = host.start()
    assert run(search, "something", DEFAULT_ACTION) == Show(text="search made no row 'something'")
    assert run(search, "none", DEFAULT_ACTION) == Show(text="Nothing matched; try other words")


# --- serve ---------------------------------------------------------------------------------------------------


def test_serve_round_trips_describe_query_and_run(host: Host) -> None:
    a = host.note("a.md")
    host.configure(provider("rg", ["n"], host.fake, "paths", a))
    search = host.start()
    requests = [
        {"id": 1, "method": "describe", "params": {"protocol": 1}},
        {"id": 2, "method": "query", "params": {"text": "n offsite"}},
        {"id": 3, "method": "query", "params": {"text": "elsewhere"}},
    ]
    sink = io.StringIO()
    serve(plugin(search), io.StringIO("".join(json.dumps(r) + "\n" for r in requests)), sink)
    described, queried, elsewhere = (json.loads(line) for line in sink.getvalue().splitlines())
    assert "keyword" not in described["result"]
    assert described["result"]["name"] == "search"
    (item,) = queried["result"]["items"]
    assert item["title"] == "a.md"
    assert "score" not in item
    assert elsewhere["result"] == {"items": []}
    ran = io.StringIO()
    run_request = {"id": 4, "method": "run", "params": {"item": item["id"], "action": "copy-path"}}
    serve(plugin(search), io.StringIO(json.dumps(run_request) + "\n"), ran)
    assert json.loads(ran.getvalue())["result"] == {"effect": {"kind": "copy", "text": a}}
