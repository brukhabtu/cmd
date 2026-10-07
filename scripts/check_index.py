# /// script
# requires-python = ">=3.12"
# ///
"""Check plugins/index.toml, the list of plugins `cmd plugin install <name>` can fetch.

Decision 8: each entry has `name` (the manifest's name, and the directory it installs to),
`summary`, `source` (a git URL) and `ref` (a commit, or a tag), and may have `subdirectory`.
A tag can be moved after review and a commit cannot, so an entry whose ref is a tag also
carries `commit`, the commit the tag pointed at when it was reviewed; the check resolves
the tag with `git ls-remote` and compares. For every entry the manifest at `ref` is
fetched with git and its name must be the entry's. Standard library and git only.

Usage: python scripts/check_index.py plugins/index.toml [--offline]
  --offline checks the shape only, for a machine without the network.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

REQUIRED = frozenset({"name", "summary", "source", "ref"})
KNOWN = REQUIRED | {"subdirectory", "commit"}
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def shape_problems(index: dict[str, Any]) -> list[str]:
    """Everything wrong with the file itself, without touching the network. Pure."""
    entries = index.get("plugin", [])
    if not isinstance(entries, list):
        return ["`plugin` must be an array of tables ([[plugin]])"]
    problems = [
        f"{label(entry)}: missing {', '.join(sorted(REQUIRED - entry.keys()))}"
        for entry in entries
        if not entry.keys() >= REQUIRED
    ]
    problems += [
        f"{label(entry)}: unknown field {', '.join(sorted(entry.keys() - KNOWN))}"
        for entry in entries
        if not entry.keys() <= KNOWN
    ]
    problems += [
        f"{label(entry)}: {field} must be a string"
        for entry in entries
        for field in sorted(KNOWN & entry.keys())
        if not isinstance(entry[field], str)
    ]
    names = [entry.get("name") for entry in entries]
    problems += [
        f"{name}: listed more than once" for name in sorted(set(names)) if names.count(name) > 1
    ]
    problems += [
        f"{label(entry)}: ref {entry['ref']!r} is a tag, "
        "so `commit` must carry the commit it was reviewed at"
        for entry in entries
        if isinstance(entry.get("ref"), str)
        and not COMMIT.match(entry["ref"])
        and "commit" not in entry
    ]
    problems += [
        f"{label(entry)}: commit {entry['commit']!r} is not a full commit hash"
        for entry in entries
        if isinstance(entry.get("commit"), str) and not COMMIT.match(entry["commit"])
    ]
    return problems


def label(entry: dict[str, Any]) -> str:
    """How an entry is named in a message: by its name, or by its position."""
    return str(entry.get("name", "an entry without a name"))


def git(*args: str) -> str:
    """Run git and return what it printed.

    Raises:
        FileNotFoundError: when git is not installed.
        RuntimeError: when git fails, with git's own message.
    """
    executable = shutil.which("git")
    if executable is None:
        message = "git is not installed"
        raise FileNotFoundError(message)
    completed = subprocess.run([executable, *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout


def manifest_name_at(source: str, ref: str, subdirectory: str | None) -> str:
    """The name in `cmd-plugin.toml` at `ref` of `source`, read from a shallow fetch."""
    path = f"{subdirectory}/cmd-plugin.toml" if subdirectory else "cmd-plugin.toml"
    with tempfile.TemporaryDirectory() as scratch:
        git("-C", scratch, "init", "-q")
        git("-C", scratch, "fetch", "-q", "--depth", "1", source, ref)
        text = git("-C", scratch, "cat-file", "-p", f"FETCH_HEAD:{path}")
    return str(tomllib.loads(text).get("name"))


def tag_commit(source: str, tag: str) -> str:
    """The commit a tag points at on the remote, through an annotated tag if it is one.

    Raises:
        RuntimeError: when the remote has no such tag.
    """
    listed = git("ls-remote", source, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    commits = {line.split("\t")[1]: line.split("\t")[0] for line in listed.splitlines()}
    peeled = commits.get(f"refs/tags/{tag}^{{}}")
    plain = commits.get(f"refs/tags/{tag}")
    commit = peeled or plain
    if commit is None:
        message = f"no tag {tag!r} at {source}"
        raise RuntimeError(message)
    return commit


def remote_problems(entry: dict[str, Any]) -> list[str]:
    """What is wrong with one well-shaped entry once the remote is asked."""
    name, source, ref = entry["name"], entry["source"], entry["ref"]
    try:
        if "commit" in entry and (found := tag_commit(source, ref)) != entry["commit"]:
            return [f"{name}: tag {ref!r} now points at {found}, not {entry['commit']}"]
        manifest_name = manifest_name_at(
            source, entry.get("commit", ref), entry.get("subdirectory")
        )
    except RuntimeError as error:
        return [f"{name}: cannot read the manifest at {ref!r}: {error}"]
    if manifest_name != name:
        return [f"{name}: the manifest at {ref!r} is named {manifest_name!r}"]
    return []


_USAGE_ERROR = 2


def main(argv: list[str]) -> int:
    """Check the shape, then every entry against its remote; the verdict is the exit code."""
    match argv:
        case [_, index_path] | [_, index_path, "--offline"]:
            index = tomllib.loads(Path(index_path).read_text(encoding="utf-8"))
        case _:
            print(__doc__, file=sys.stderr)
            return _USAGE_ERROR
    problems = shape_problems(index)
    if argv[-1] == "--offline":
        print(f"{len(index.get('plugin', []))} entries, shape only: no network")
    elif not problems:
        for entry in index.get("plugin", []):
            problems += remote_problems(entry)
            print(f"{entry['name']}: {entry['source']} at {entry['ref']}")
    for problem in problems:
        print(f"index: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
