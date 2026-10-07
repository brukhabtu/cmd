"""Tests for hooks/context.py.

The first half tests the logic with plain values. The second half runs the hook as a
subprocess, the way Claude Code does, against throwaway git repositories and a
throwaway temp directory. Set HOOK_PYTHON to run the hook under another interpreter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import context  # noqa: E402
from context import Mode, Rule  # noqa: E402

HOOK_PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)
OWNERS = ("github.com/bruk-io/", "github.com/brukhabtu/")


# --- logic ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "globs", "expected"),
    [
        ("/repo/src/app/core.py", ("**/*.py",), True),
        ("core.py", ("**/*.py",), True),
        ("/repo/src/app/core.pyc", ("**/*.py",), False),
        ("/repo/pyproject.toml", ("**/pyproject.toml",), True),
        ("/repo/tests/unit/test_core.py", ("**/tests/**/*.py",), True),
        ("/repo/tests/test_core.py", ("**/tests/**/*.py",), True),
        ("/repo/src/test_core.py", ("**/test_*.py",), True),
        ("/repo/src/contest.py", ("**/test_*.py", "**/conftest.py"), False),
        ("/repo/.claude/rules/py/style.md", ("**/.claude/rules/**",), True),
        ("/repo/.claude/worktrees/a/README.md", ("**/.claude/rules/**",), False),
        ("/repo/.claude/settings.local.json", ("**/.claude/settings*.json",), True),
        ("/repo/skills/x/SKILL.md", ("**/SKILL.md",), True),
        ("C:\\repo\\src\\core.py", ("**/*.py",), True),
    ],
)
def test_matches(path: str, globs: tuple[str, ...], expected: bool) -> None:
    assert context.matches(path, globs) is expected


def test_parse_rule_reads_paths_and_mode() -> None:
    text = '---\npaths:\n  - "**/*.py"\n  - "**/pyproject.toml"\nmode: owner\n---\n# Python\n\nBody.\n'
    rule = context.parse_rule("python", text)
    assert rule == Rule("python", ("**/*.py", "**/pyproject.toml"), True, "# Python\n\nBody.")


def test_parse_rule_without_frontmatter_matches_nothing() -> None:
    rule = context.parse_rule("plain", "# Plain\n")
    assert rule.paths == () and rule.owner_only is False


@pytest.mark.parametrize(
    "remote",
    [
        "git@github.com:bruk-io/bunk.git",
        "https://github.com/bruk-io/bunk.git",
        "ssh://git@github.com/bruk-io/bunk.git",
    ],
)
def test_normalise_remote_gives_one_form(remote: str) -> None:
    assert context.normalise_remote(remote) == "github.com/bruk-io/bunk.git"


def test_parse_owners_skips_comments_and_blanks() -> None:
    assert context.parse_owners("# mine\n\ngithub.com/a/  # trailing\ngithub.com/b/\n") == (
        "github.com/a/",
        "github.com/b/",
    )


def test_repo_mode() -> None:
    assert context.repo_mode("git@github.com:bruk-io/bunk.git", OWNERS) is Mode.OWNER
    assert context.repo_mode("https://github.corp.ebay.com/live/ios_core", OWNERS) is Mode.GUEST
    assert context.repo_mode(None, OWNERS) is Mode.OWNER


def test_rules_to_inject_filters_seen_and_guest() -> None:
    python = Rule("python", ("**/*.py",), True, "p")
    tooling = Rule("agent-tooling", ("**/SKILL.md",), False, "t")
    rules = (python, tooling)
    pick = context.rules_to_inject
    assert pick(rules, "/r/a.py", Mode.OWNER, frozenset()) == (python,)
    assert pick(rules, "/r/a.py", Mode.OWNER, frozenset({"python"})) == ()
    assert pick(rules, "/r/a.py", Mode.GUEST, frozenset()) == ()
    assert pick(rules, "/r/SKILL.md", Mode.GUEST, frozenset()) == (tooling,)


def test_every_shipped_rule_can_load() -> None:
    rules = context.load_rules(ROOT)
    assert {r.name for r in rules} == {"python", "python-tests", "agent-tooling"}
    assert all(r.paths and r.body for r in rules)
    assert {r.name for r in rules if r.owner_only} == {"python", "python-tests"}


# --- the hook as Claude Code runs it ---------------------------------------------------


def make_repo(path: Path, remote: str | None) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
    return path


@pytest.fixture
def owned(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "owned", "git@github.com:bruk-io/bunk.git")


@pytest.fixture
def guest(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "guest", "https://github.corp.ebay.com/live/ios_core.git")


def run_hook(tmp_path: Path, payload: dict | str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TMPDIR=str(tmp_path / "tmp"), CLAUDE_PLUGIN_ROOT=str(ROOT))
    (tmp_path / "tmp").mkdir(exist_ok=True)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [HOOK_PYTHON, str(ROOT / "hooks" / "context.py")],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


def start(cwd: Path, source: str = "startup", session: str = "s1") -> dict:
    return {"hook_event_name": "SessionStart", "session_id": session, "cwd": str(cwd), "source": source}


def touch(cwd: Path, file: str, session: str = "s1", **extra: str) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "session_id": session,
        "cwd": str(cwd),
        "tool_name": "Read",
        "tool_input": {"file_path": str(cwd / file)},
        **extra,
    }


def injected(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return ""
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    return str(output["additionalContext"])


def test_session_start_in_owned_repo(tmp_path: Path, owned: Path) -> None:
    result = run_hook(tmp_path, start(owned))
    assert result.returncode == 0
    assert result.stdout.startswith("[philosophy] Repository mode: owner.")
    assert "# Standing constraints" in result.stdout
    assert "{plugin_root}" not in result.stdout
    assert str(ROOT / "docs" / "engineering-philosophy.md") in result.stdout
    assert (ROOT / "docs" / "engineering-philosophy.md").exists()


def test_session_start_in_guest_repo(tmp_path: Path, guest: Path) -> None:
    result = run_hook(tmp_path, start(guest))
    assert "Repository mode: guest (origin: github.corp.ebay.com/live/ios_core.git)" in result.stdout
    assert "# Standing constraints" in result.stdout


def test_session_start_outside_git_is_owner(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert "Repository mode: owner." in run_hook(tmp_path, start(plain)).stdout


def test_python_rule_arrives_once_per_session(tmp_path: Path, owned: Path) -> None:
    first = injected(run_hook(tmp_path, touch(owned, "src/core.py")))
    assert "[philosophy] rule python" in first and "## Floor and tools" in first
    assert "python-tests" not in first
    assert injected(run_hook(tmp_path, touch(owned, "src/other.py"))) == ""
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "src/core.py", session="s2")))


def test_test_file_gets_both_python_rules(tmp_path: Path, owned: Path) -> None:
    text = injected(run_hook(tmp_path, touch(owned, "tests/unit/test_core.py")))
    assert "[philosophy] rule python\n" in text and "[philosophy] rule python-tests\n" in text


def test_compact_lets_rules_load_again(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    assert injected(run_hook(tmp_path, touch(owned, "a.py"))) == ""
    run_hook(tmp_path, start(owned, source="compact"))
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py")))


def test_resume_does_not_reload_rules(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    run_hook(tmp_path, start(owned, source="resume"))
    assert injected(run_hook(tmp_path, touch(owned, "a.py"))) == ""


def test_subagent_gets_its_own_copy(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py", agent_id="worker-1")))
    assert injected(run_hook(tmp_path, touch(owned, "a.py", agent_id="worker-1"))) == ""


def test_guest_repo_gets_no_python_rules(tmp_path: Path, guest: Path) -> None:
    assert injected(run_hook(tmp_path, touch(guest, "src/core.py"))) == ""
    assert injected(run_hook(tmp_path, touch(guest, "tests/test_core.py"))) == ""


def test_guest_repo_still_gets_agent_tooling(tmp_path: Path, guest: Path) -> None:
    text = injected(run_hook(tmp_path, touch(guest, ".claude/skills/x/SKILL.md")))
    assert "[philosophy] rule agent-tooling" in text


def test_unrelated_file_injects_nothing(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "README.md"))) == ""
    assert injected(run_hook(tmp_path, touch(owned, ".claude/worktrees/a/notes.md"))) == ""


def test_tool_without_a_file_injects_nothing(tmp_path: Path, owned: Path) -> None:
    payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(owned), "tool_input": {}}
    assert injected(run_hook(tmp_path, payload)) == ""


def test_bad_input_never_breaks_the_session(tmp_path: Path) -> None:
    result = run_hook(tmp_path, "this is not json")
    assert result.returncode == 0
    assert result.stdout == ""
    assert "[philosophy] hook skipped" in result.stderr
