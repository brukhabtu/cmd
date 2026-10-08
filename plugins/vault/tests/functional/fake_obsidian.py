"""A fake obsidian CLI: the tests copy it into a temporary directory and point obsidian.bin at it.

It speaks the commands the plugin's guesses use (``daily:append``, ``daily:read``, ``read``,
``create``, ``append``, ``search``, ``open``, with ``key=value`` parameters) against a vault
directory, and logs every call. ``state.json`` beside it says how it behaves:

- ``working``: does what it is asked.
- ``closed``: fails at once with a readable message, as a CLI without a running Obsidian might.
- ``failing``: exits 2 with an error on stderr.
- ``slow``: sleeps far past any deadline before doing anything.
- ``landing``: does a write, then sleeps far past any deadline: the write landed, the call
  was killed.

A test flips the mode between calls, which is how the CLI recovers.
"""

import datetime
import json
import sys
import time
from pathlib import Path

_SLEEP = 30.0


def _insert(note: str, line: str, heading: str | None) -> str:
    """The note with ``line`` at the end of the ``heading`` section, or at its end."""
    lines = note.splitlines()
    if heading is None:
        return "\n".join([*lines, line]) + "\n"
    for index, existing in enumerate(lines):
        level = len(existing) - len(existing.lstrip("#"))
        if level and existing[level:].strip() == heading:
            end = index + 1
            while end < len(lines):
                other = len(lines[end]) - len(lines[end].lstrip("#"))
                if other and other <= level:
                    break
                end += 1
            while end > index + 1 and not lines[end - 1].strip():
                end -= 1
            return "\n".join([*lines[:end], line, *lines[end:]]) + "\n"
    return "\n".join([*lines, f"## {heading}", line]) + "\n"


def _fail(message: str, code: int = 1) -> int:
    sys.stderr.write(message + "\n")
    return code


def main() -> int:
    """Do one call, as the mode says."""
    here = Path(__file__).resolve().parent
    state = json.loads((here / "state.json").read_text(encoding="utf-8"))
    arguments = sys.argv[1:]
    with (here / "calls.log").open("a", encoding="utf-8") as log:
        log.write(json.dumps(arguments) + "\n")
    mode = state["mode"]
    if mode == "closed":
        return _fail("Error: Obsidian is not running. Open Obsidian and try again.")
    if mode == "failing":
        return _fail("Error: something went wrong in the vault\nmore detail", 2)
    if mode == "slow":
        time.sleep(_SLEEP)
    params = dict(word.partition("=")[::2] for word in arguments if "=" in word)
    words = [word for word in arguments if "=" not in word]
    vault = Path(state["vault"])
    daily = vault / "Daily" / f"{datetime.datetime.now().astimezone().date().isoformat()}.md"
    command = words[0]
    note = daily if command.startswith("daily:") else vault / params.get("path", "")
    code = _command(command, note, params, vault)
    if mode == "landing" and command in {"append", "daily:append", "create"}:
        time.sleep(_SLEEP)
    return code


def _command(command: str, note: Path, params: dict[str, str], vault: Path) -> int:  # ruff: ignore[complex-structure] - one branch per command the fake speaks
    match command:
        case "read" | "daily:read":
            if not note.is_file():
                return _fail(f"Error: file not found: {note.name}")
            sys.stdout.write(note.read_text(encoding="utf-8"))
        case "create":
            if note.exists():
                return _fail(f"Error: {note.name} already exists")
            note.parent.mkdir(parents=True, exist_ok=True)
            template = params.get("template")
            note.write_text(f"made from {template}\n" if template else "", encoding="utf-8")
        case "append" | "daily:append":
            if command == "append" and not note.is_file():
                return _fail(f"Error: file not found: {note.name}")
            note.parent.mkdir(parents=True, exist_ok=True)
            before = note.read_text(encoding="utf-8") if note.exists() else ""
            after = _insert(before, params["content"], params.get("heading"))
            note.write_text(after, encoding="utf-8")
        case "search":
            wanted = params["query"].casefold()
            for path in sorted(vault.rglob("*.md")):
                if (
                    wanted in path.read_text(encoding="utf-8").casefold()
                    or wanted in path.name.casefold()
                ):
                    sys.stdout.write(f"{path.relative_to(vault)}\n")
        case "open":
            pass
        case _:
            return _fail(f"Error: unknown command {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
