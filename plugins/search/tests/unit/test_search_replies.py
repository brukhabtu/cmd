"""Routing, the plugin's own rows, what an id means, and the memory's cache and rest."""

from dataclasses import dataclass

from search.hits import Failed, Found, Hit
from search.memory import CACHE_SECONDS, CACHE_SIZE, REST_SECONDS, Memory
from search.merge import Called, Target, Unstarted, encode
from search.replies import (
    Detail,
    Keyword,
    OnHit,
    OpenConfig,
    Say,
    Startup,
    Status,
    choice,
    route,
    status_rows,
)
from search.settings import Problem, Settings, parse, unusable

QMD = {"name": "qmd", "kind": "qmd", "keywords": ["n", "qmd"], "bin": "/q"}
RG = {
    "name": "rg",
    "kind": "command",
    "keywords": ["n", "grep"],
    "command": ["/rg", "{text}"],
    "format": "paths",
}
SETTINGS = parse({"provider": [QMD, RG, {"name": "bad", "keywords": ["broken"]}]})


# --- routing --------------------------------------------------------------------------------------


def test_a_first_word_that_is_no_keyword_routes_nowhere() -> None:
    assert route("hello world", SETTINGS) is None
    assert route("   ", SETTINGS) is None
    assert route("nn offsite", SETTINGS) is None


def test_the_status_keyword_case_ignored() -> None:
    assert route("SEARCH", SETTINGS) == Status()


def test_a_keyword_selects_every_provider_that_lists_it_in_config_order() -> None:
    found = route("N  offsite budget ", SETTINGS)
    assert isinstance(found, Keyword)
    assert [provider.name for provider in found.providers] == ["qmd", "rg"]
    assert found.text == "offsite budget"
    assert found.typed == "N"
    found = route("grep x", SETTINGS)
    assert isinstance(found, Keyword)
    assert [provider.name for provider in found.providers] == ["rg"]


def test_an_invalid_providers_keyword_routes_to_its_problem() -> None:
    found = route("broken x", SETTINGS)
    assert isinstance(found, Keyword)
    assert found.providers == ()
    ((position, problem),) = found.problems
    assert position == 0
    assert problem.message.startswith("bad: kind: must be set")


# --- the status rows ------------------------------------------------------------------------------------


def test_the_status_rows_list_providers_last_outcomes_and_problems() -> None:
    settings = unusable(SETTINGS, "rg", "rg: /rg is not an executable file")
    startup = Startup(settings, "/config")
    last = {"qmd": Called(Found((Hit("a"),)), 0, timed_out=False)}
    rows = status_rows(startup, last)
    assert [row.id for row in rows] == [
        "status",
        "provider:qmd",
        "provider:rg",
        "config:0",
        "config:1",
    ]
    assert rows[0].title == "search: 2 providers"
    assert rows[0].subtitle == "keywords: n, qmd, grep, broken"
    assert rows[1].title == "qmd: qmd on n, qmd"
    assert rows[1].subtitle == "last search: 1 hit"
    assert rows[2].subtitle == "rg: /rg is not an executable file"
    assert rows[4].title == "rg: /rg is not an executable file"


def test_the_status_rows_with_no_config() -> None:
    startup = Startup(Settings(problems=(Problem("No config: create config.toml in /c"),)), "/c")
    rows = status_rows(startup, {})
    assert [(row.id, row.title) for row in rows] == [
        ("status", "search: 0 providers"),
        ("config:0", "No config: create config.toml in /c"),
    ]


# --- what an id means -----------------------------------------------------------------------------------


def test_each_kind_of_id() -> None:
    target = Target("t", ("qmd",), 0, path="/a")
    assert choice(encode(target)) == OnHit(target)
    assert choice("config:3") == OpenConfig()
    assert choice("problem:qmd") == Detail("qmd")
    assert choice("provider:rg") == Detail("rg")
    assert isinstance(choice("hint:min"), Say)
    assert isinstance(choice("none"), Say)
    assert isinstance(choice("status"), Say)
    assert choice("elsewhere") == Say("search made no row 'elsewhere'")
    assert choice("{broken") == Say("search made no row '{broken'")


# --- the memory --------------------------------------------------------------------------------------------


@dataclass
class Ticks:
    now: float = 1000.0

    def __call__(self) -> float:
        return self.now


ANSWER = Called(Found((Hit("a"),)), 0, timed_out=False)
LATE = Called(Found((), cut=True), None, timed_out=True)


def test_an_answer_in_time_is_kept_ten_seconds() -> None:
    ticks = Ticks()
    memory = Memory(ticks)
    memory.record("qmd", "offsite", ANSWER)
    assert memory.cached("qmd", "offsite") == ANSWER
    assert memory.cached("qmd", "offsit") is None
    assert memory.cached("rg", "offsite") is None
    ticks.now += CACHE_SECONDS
    assert memory.cached("qmd", "offsite") is None


def test_a_failure_in_time_is_kept_too() -> None:
    memory = Memory(Ticks())
    memory.record("qmd", "x", Called(Failed("Collection not found: x"), 1, timed_out=False))
    memory.record("rg", "x", Unstarted("cannot run /rg"))
    assert memory.cached("qmd", "x") is not None
    assert memory.cached("rg", "x") is not None


def test_a_timed_out_call_is_not_kept_and_three_rest_the_provider() -> None:
    ticks = Ticks()
    memory = Memory(ticks)
    for text in ("a", "b"):
        memory.record("rg", text, LATE)
        assert memory.cached("rg", text) is None
        assert memory.resting("rg") is None
    memory.record("rg", "c", LATE)
    assert memory.resting("rg") == REST_SECONDS
    ticks.now += REST_SECONDS - 1
    assert memory.resting("rg") == 1
    ticks.now += 1
    assert memory.resting("rg") is None


def test_a_call_in_time_sets_the_count_back() -> None:
    memory = Memory(Ticks())
    memory.record("rg", "a", LATE)
    memory.record("rg", "b", LATE)
    memory.record("rg", "c", ANSWER)
    memory.record("rg", "d", LATE)
    memory.record("rg", "e", LATE)
    assert memory.resting("rg") is None


def test_no_more_than_the_cache_size_is_kept() -> None:
    memory = Memory(Ticks())
    for n in range(CACHE_SIZE + 5):
        memory.record("rg", str(n), ANSWER)
    assert memory.cached("rg", "0") is None
    assert memory.cached("rg", str(CACHE_SIZE + 4)) == ANSWER


def test_the_last_call_keeps_its_command_and_stderrs_first_five_lines() -> None:
    memory = Memory(Ticks())
    memory.started("rg", "/rg -- offsite")
    memory.record("rg", "offsite", ANSWER, "1\n2\n3\n4\n5\n6\n")
    last = memory.last("rg")
    assert last is not None
    assert (last.command, last.stderr, last.report) == ("/rg -- offsite", "1\n2\n3\n4\n5", ANSWER)
    assert memory.reports() == {"rg": ANSWER}
