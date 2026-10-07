#!/usr/bin/env python3
"""Put the plugin's constraints and rules in front of the model.

Claude Code does not load a plugin's CLAUDE.md or rules/, so this hook does it:

- SessionStart: prints the repository mode (owner or guest) and constraints.md. Stdout
  from a SessionStart hook becomes context.
- PostToolUse on a file tool: the first time a file matching a rule's `paths` is touched
  in a session, returns that rule as additionalContext.

Written for Python 3.9, because hooks run under whatever `python3` is on PATH. A hook
must never break the session, so every failure exits 0 with the reason on stderr.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional

PLUGIN = "philosophy"
FILE_KEYS = ("file_path", "notebook_path")


class Mode(Enum):
    OWNER = "owner"
    GUEST = "guest"


class Rule(NamedTuple):
    name: str
    paths: tuple[str, ...]
    owner_only: bool
    body: str


# --- the logic: plain data in, plain data out ---------------------------------------


def glob_to_regex(glob: str) -> str:
    """Translate a rule glob into a regex that matches a whole POSIX path.

    `**/` matches any number of directories (including none), `**` matches anything,
    `*` matches within one path segment, and `?` matches one character.
    """
    out = []
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return "".join(out)


def matches(path: str, globs: tuple[str, ...]) -> bool:
    """Say whether a path matches any glob. A relative glob may match at any depth."""
    posix = path.replace("\\", "/")
    return any(re.fullmatch("(?:.*/)?" + glob_to_regex(g), posix) for g in globs)


def parse_rule(name: str, text: str) -> Rule:
    """Read a rule file: `paths` and `mode` from the frontmatter, the rest as the body.

    Only the two keys this plugin uses are understood. A rule with no `paths` matches
    nothing and is never injected.
    """
    paths: list[str] = []
    owner_only = False
    body = text
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        front, body = text[4:].split("\n---\n", 1)
        in_paths = False
        for line in front.splitlines():
            if line.startswith("paths:"):
                in_paths = True
            elif in_paths and line.lstrip().startswith("- "):
                paths.append(line.lstrip()[2:].strip().strip("\"'"))
            else:
                in_paths = False
                if line.startswith("mode:"):
                    owner_only = line.split(":", 1)[1].strip() == Mode.OWNER.value
    return Rule(name, tuple(paths), owner_only, body.strip())


def normalise_remote(remote: str) -> str:
    """Reduce a git remote URL to `host/owner/repo` so one pattern covers SSH and HTTPS."""
    url = remote.strip()
    url = re.sub(r"^[a-z+]+://", "", url)
    url = re.sub(r"^[^@/]+@", "", url)
    return url.replace(":", "/", 1) if "/" not in url.split(":", 1)[0] else url


def parse_owners(text: str) -> tuple[str, ...]:
    """Read owners.txt: one pattern per line, with `#` comments and blank lines ignored."""
    lines = (line.split("#", 1)[0].strip() for line in text.splitlines())
    return tuple(line for line in lines if line)


def repo_mode(remote: Optional[str], owners: tuple[str, ...]) -> Mode:
    """Decide the mode. No remote means a local repository, which is the owner's."""
    if remote is None:
        return Mode.OWNER
    normalised = normalise_remote(remote)
    return Mode.OWNER if any(owner in normalised for owner in owners) else Mode.GUEST


def rules_to_inject(
    rules: tuple[Rule, ...], path: str, mode: Mode, seen: frozenset[str]
) -> tuple[Rule, ...]:
    """Pick the rules that match the path, apply in this mode, and are not yet in context."""
    return tuple(
        rule
        for rule in rules
        if rule.name not in seen
        and not (rule.owner_only and mode is Mode.GUEST)
        and matches(path, rule.paths)
    )


def session_text(mode: Mode, remote: Optional[str], constraints: str, root: str) -> str:
    """Build what SessionStart prints: the mode line, then the constraints."""
    if mode is Mode.OWNER:
        line = "Repository mode: owner. The full standard applies here."
    else:
        line = (
            "Repository mode: guest (origin: %s). The local style governs, and the "
            "plugin's Python dialect rules are not loaded." % normalise_remote(remote or "")
        )
    return "[%s] %s\n\n%s" % (PLUGIN, line, constraints.replace("{plugin_root}", root).strip())


def rule_text(rules: tuple[Rule, ...]) -> str:
    """Build the additionalContext for the rules being injected."""
    return "\n\n".join("[%s] rule %s\n\n%s" % (PLUGIN, r.name, r.body) for r in rules)


# --- the shell: the only code that touches git, the filesystem, or stdio -------------


def plugin_root() -> Path:
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)


def origin(cwd: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def marker_dir(payload: dict) -> Path:
    agent = str(payload.get("agent_id") or "main")
    session = re.sub(r"[^\w.-]", "_", str(payload.get("session_id") or "unknown"))
    return Path(tempfile.gettempdir()) / ("claude-%s-plugin" % PLUGIN) / session / agent


def load_rules(root: Path) -> tuple[Rule, ...]:
    return tuple(parse_rule(p.stem, p.read_text()) for p in sorted((root / "rules").glob("*.md")))


def current_mode(root: Path, cwd: str) -> tuple[Mode, Optional[str]]:
    owners_file = root / "owners.txt"
    owners = parse_owners(owners_file.read_text()) if owners_file.exists() else ()
    remote = origin(cwd)
    return repo_mode(remote, owners), remote


def on_session_start(payload: dict, root: Path) -> None:
    if payload.get("source") in ("clear", "compact"):
        # The rules injected earlier are gone from context, so let them load again.
        session = marker_dir(payload).parent
        for marker in session.glob("*/*.seen"):
            marker.unlink()
    mode, remote = current_mode(root, str(payload.get("cwd") or os.getcwd()))
    print(session_text(mode, remote, (root / "constraints.md").read_text(), str(root)))


def on_tool_use(payload: dict, root: Path) -> None:
    tool_input = payload.get("tool_input") or {}
    path = next((tool_input[k] for k in FILE_KEYS if tool_input.get(k)), None)
    if not path:
        return
    markers = marker_dir(payload)
    seen = frozenset(p.stem for p in markers.glob("*.seen")) if markers.exists() else frozenset()
    mode, _ = current_mode(root, str(payload.get("cwd") or os.getcwd()))
    chosen = rules_to_inject(load_rules(root), str(path), mode, seen)
    if not chosen:
        return
    markers.mkdir(parents=True, exist_ok=True)
    for rule in chosen:
        (markers / (rule.name + ".seen")).touch()
    output = {"hookEventName": "PostToolUse", "additionalContext": rule_text(chosen)}
    print(json.dumps({"hookSpecificOutput": output}))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        root = plugin_root()
        if payload.get("hook_event_name") == "SessionStart":
            on_session_start(payload, root)
        elif payload.get("hook_event_name") == "PostToolUse":
            on_tool_use(payload, root)
    except Exception as error:  # noqa: BLE001 - a hook must never break the session
        print("[%s] hook skipped: %s: %s" % (PLUGIN, type(error).__name__, error), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
