"""Generate the parts of the documentation site that come from the repository itself.

MkDocs runs this through the gen-files plugin on every build, so these pages cannot drift
from the code: the Python API pages (rendered by mkdocstrings from the docstrings), an
overview of the Rust crates from their `//!` module docs, the Rust API reference that
`cargo doc` built, the plugin catalogue from plugins/index.toml and each plugin's own
files, the decisions from backlog/decisions, and the CLI usage from the binaries' usage
text. The functions that read and shape are pure; `main` is the thin shell that writes.
"""

import ast
import importlib
import json
import logging
import os
import re
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

REPOSITORY = Path(__file__).resolve().parent.parent
GITHUB = "https://github.com/brukhabtu/cmd/tree/ccr-16512bde-x72oqp"
PYTHON_ROOTS = (
    ("The SDK", REPOSITORY / "python" / "cmd-sdk" / "src"),
    ("Example plugins", REPOSITORY / "plugins"),
)
RUST_LIBRARIES = ("cmd_core", "cmd_host")
# Under the mkdocs logger, so a warning here fails `mkdocs build --strict`.
LOG = logging.getLogger("mkdocs.plugins.docs_gen")

Opener = Callable[[str, str], IO[Any]]


# --- Python modules ---------------------------------------------------------------------


def python_modules(package_dir: Path) -> list[str]:
    """The importable modules of one package, by dotted name: the package, then each module.

    Private modules (a leading underscore) and tests are left out: the reference is for
    what a plugin author may import.
    """
    package = package_dir.name
    names = [package]
    for path in sorted(package_dir.rglob("*.py")):
        relative = path.relative_to(package_dir).with_suffix("")
        parts = relative.parts
        if parts[-1] == "__init__" or any(part.startswith("_") for part in parts):
            continue
        names.append(".".join((package, *parts)))
    return names


def plugin_packages(plugins_dir: Path) -> list[Path]:
    """Each plugin's package directory, found as plugins/<plugin>/src/<package>/__init__.py."""
    return sorted(init.parent for init in plugins_dir.glob("*/src/*/__init__.py"))


def sdk_packages(src: Path) -> list[Path]:
    """The SDK's package directories under its src root."""
    return sorted(init.parent for init in src.glob("*/__init__.py"))


def module_page(name: str) -> str:
    """The Markdown of one API page: a heading and the mkdocstrings directive."""
    return f"# `{name}`\n\n::: {name}\n"


# --- Rust crates ------------------------------------------------------------------------


def module_docs(text: str) -> str:
    """The `//!` documentation at the top of a Rust file, as Markdown.

    rustdoc's intra-doc links (`[`Host`]`) become code spans, since the site cannot
    resolve them.
    """
    lines = []
    for line in text.splitlines():
        if line.startswith("//!"):
            lines.append(line[3:].removeprefix(" "))
        elif lines or line.strip():
            break
    docs = "\n".join(lines).strip()
    return re.sub(r"\[(`[^`]+`)\](?!\()", r"\1", docs)


def declared_modules(text: str) -> list[str]:
    """The modules a crate root declares with `mod` or `pub mod`, in order."""
    return re.findall(r"^\s*(?:pub\s+)?mod\s+([a-z_][a-z0-9_]*)\s*;", text, flags=re.MULTILINE)


@dataclass(frozen=True)
class Crate:
    """One crate of the workspace, as the overview shows it."""

    name: str
    root: str
    docs: str
    modules: tuple[tuple[str, str], ...]


def crate_overview(crate_dir: Path) -> Crate:
    """Read a crate's root file and each module's docs. Pure apart from reading the files."""
    src = crate_dir / "src"
    root = src / "lib.rs" if (src / "lib.rs").exists() else src / "main.rs"
    text = root.read_text(encoding="utf-8")
    modules = []
    for module in declared_modules(text):
        path = src / f"{module}.rs"
        if path.exists():
            modules.append((module, module_docs(path.read_text(encoding="utf-8"))))
    return Crate(crate_dir.name, root.name, module_docs(text), tuple(modules))


def crates_page(crates: list[Crate], rustdoc_built: set[str]) -> str:
    """The overview of every crate, with a link to its rustdoc where one was built."""
    out = [
        "# The crates",
        "",
        "Generated from each crate's `//!` module documentation on every build. The full API",
        "reference for the library crates is [rustdoc's](rust-api.md).",
    ]
    for crate in crates:
        out += ["", f"## `{crate.name}`", "", f"*Root:* `crates/{crate.name}/src/{crate.root}`"]
        library = crate.name.replace("-", "_")
        if library in rustdoc_built:
            out += ["", f"[API reference](../reference/rust/{library}/index.html)"]
        out += ["", crate.docs or "*No module documentation yet.*"]
        for module, docs in crate.modules:
            summary = docs.split("\n\n")[0].replace("\n", " ") if docs else "*No module docs.*"
            out += ["", f"- **`{module}`**: {summary}"]
    return "\n".join(out) + "\n"


def rust_api_page(rustdoc_built: set[str]) -> str:
    """The page that leads to rustdoc's output, or says how to build it."""
    out = [
        "# Rust API reference",
        "",
        "rustdoc builds this from the library crates' doc comments; `scripts/docs.sh` runs",
        "`cargo doc` before the site is built. `cmd-app` is a binary that only builds on macOS,",
        "so its documentation is the [crate overview](crates.md).",
        "",
    ]
    if rustdoc_built:
        out += [
            f"- [`{name}`](../reference/rust/{name}/index.html)" for name in sorted(rustdoc_built)
        ]
    else:
        out += [
            '!!! note "Not built in this run"',
            "    `cargo doc` had not run, so there is no rustdoc output to link. Build the site",
            "    with `scripts/docs.sh` to include it.",
        ]
    return "\n".join(out) + "\n"


# --- The CLI ----------------------------------------------------------------------------


def rust_string_constant(text: str, name: str) -> str | None:
    """The value of `const NAME: &str = "...";` in Rust source, with its escapes applied."""
    match = re.search(rf'const\s+{name}\s*:\s*&str\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', text, re.DOTALL)
    if match is None:
        return None
    raw = match.group(1)
    raw = re.sub(r"\\\n\s*", "", raw)  # a backslash at a line end joins the lines
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
    return re.sub(r"\\(.)", lambda m: escapes.get(m.group(1), m.group(0)), raw)


def cli_page(commands: list[tuple[str, str]]) -> str:
    """The CLI reference: each command's usage text, as its binary prints it."""
    out = [
        "# Command line",
        "",
        "Generated from the usage text in the source, which is what the binaries print. The",
        "same subcommands answer as `cmd plugin ...` from the app binary and as `cmd-plugin ...`",
        "from a clone.",
    ]
    for title, usage in commands:
        out += ["", f"## {title}", "", "```text", usage.strip(), "```"]
    return "\n".join(out) + "\n"


# --- Decisions --------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    """One architecture decision record from backlog/decisions."""

    id: str
    title: str
    date: str
    status: str
    body: str


def front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split Backlog.md's YAML front matter from the body.

    Only what the board writes is understood: `key: value`, quoted values, and folded
    (`>-`, `>`) or literal (`|`) values continued on indented lines.
    """
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---\n")
    fields: dict[str, str] = {}
    key = None
    for line in head.splitlines():
        if key and line.startswith((" ", "\t")):
            fields[key] = f"{fields[key]} {line.strip()}".strip()
            continue
        name, separator, value = line.partition(":")
        if not separator or not name or name.startswith(" "):
            key = None
            continue
        key, value = name.strip(), value.strip()
        fields[key] = "" if value in {">-", ">", "|", "|-"} else value.strip("'\"")
    return fields, body.lstrip("\n")


def decision(path: Path) -> Decision:
    """Read one decision file."""
    fields, body = front_matter(path.read_text(encoding="utf-8"))
    return Decision(
        id=fields.get("id", path.stem.split(" ")[0]),
        title=fields.get("title", path.stem),
        date=fields.get("date", ""),
        status=fields.get("status", ""),
        body=body,
    )


def decision_number(item: Decision) -> int:
    """Order decisions by their number, not as strings."""
    digits = re.findall(r"\d+", item.id)
    return int(digits[0]) if digits else 0


def decision_page(item: Decision) -> str:
    """One decision as a page: its title, its status line and its body unchanged."""
    meta = f"*{item.id} · {item.status or 'no status'} · {item.date}*"
    return f"# {item.title}\n\n{meta}\n\n{item.body.rstrip()}\n"


def decisions_index(items: list[Decision]) -> str:
    """The table of every decision, newest number last."""
    rows = [f"| [{d.id}]({d.id}.md) | {d.title} | {d.status} | {d.date} |" for d in items]
    return (
        "\n".join([
            "# Decisions",
            "",
            "Generated from `backlog/decisions/` on every build. A decision is proposed by whoever",
            "does the design work and accepted by the owner.",
            "",
            "| Decision | Title | Status | Date |",
            "|---|---|---|---|",
            *rows,
        ])
        + "\n"
    )


# --- The plugin catalogue ---------------------------------------------------------------


@dataclass(frozen=True)
class Listed:
    """A plugin as the index lists it and its own files describe it."""

    name: str
    summary: str
    description: str
    keyword: str | None
    command: str
    subdirectory: str


def description_keyword(source: str) -> str | None:
    """The `keyword=` a plugin passes to `Description(...)`, read from its source with ast."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Description":
            for argument in node.keywords:
                if argument.arg == "keyword" and isinstance(argument.value, ast.Constant):
                    return str(argument.value.value)
    return None


def listed_plugins(repository: Path) -> list[Listed]:
    """Every plugin the index lists, with what its manifest, pyproject and code say."""
    index = tomllib.loads((repository / "plugins" / "index.toml").read_text(encoding="utf-8"))
    listed = []
    for entry in index.get("plugin", []):
        directory = repository / entry.get("subdirectory", "")
        manifest = tomllib.loads((directory / "cmd-plugin.toml").read_text(encoding="utf-8"))
        project = tomllib.loads((directory / "pyproject.toml").read_text(encoding="utf-8"))
        keyword = None
        for init in sorted(directory.glob("src/*/__init__.py")):
            keyword = keyword or description_keyword(init.read_text(encoding="utf-8"))
        listed.append(
            Listed(
                name=entry["name"],
                summary=entry["summary"],
                description=project.get("project", {}).get("description", ""),
                keyword=keyword,
                command=" ".join(manifest["command"]),
                subdirectory=entry.get("subdirectory", ""),
            )
        )
    return listed


def catalogue_page(listed: list[Listed]) -> str:
    """The users' view: what each plugin in the index does and how to get it."""
    out = [
        "# Plugins in the index",
        "",
        "Generated from `plugins/index.toml` and each plugin's own files on every build.",
        "Install one with `cmd plugin install <name>` (see [Plugins](plugins.md)).",
        "",
        "| Plugin | What it does | Type first | Install |",
        "|---|---|---|---|",
    ]
    for item in listed:
        trigger = f"`{item.keyword}`" if item.keyword else "nothing: it answers any text"
        out.append(
            f"| **{item.name}** | {item.summary} | {trigger} | `cmd plugin install {item.name}` |"
        )
    return "\n".join(out) + "\n"


def examples_page(listed: list[Listed]) -> str:
    """The plugin authors' view: each plugin here as a worked example to read."""
    out = [
        "# Example plugins",
        "",
        "Every plugin in this repository is a small, complete example. Generated from the index",
        "and each plugin's files on every build; their API pages are under",
        "[SDK reference](../reference/python/index.md).",
    ]
    for item in listed:
        keyword = f"keyword `{item.keyword}`" if item.keyword else "no keyword (global)"
        out += [
            "",
            f"## {item.name}",
            "",
            item.description,
            "",
            f"- Source: [`{item.subdirectory}`]({GITHUB}/{item.subdirectory})",
            f"- Starts with: `{item.command}`",
            f"- Routing: {keyword}",
        ]
    return "\n".join(out) + "\n"


# --- The shell ----------------------------------------------------------------------------


def rustdoc_dir() -> Path:
    """Where `cargo doc` wrote, honouring CARGO_TARGET_DIR as cargo does."""
    target = Path(os.environ.get("CARGO_TARGET_DIR", REPOSITORY / "target"))
    return target / "doc"


def rustdoc_crates(crates_js: str) -> list[str]:
    """The crates rustdoc's shared crate list names, read from its crates.js."""
    match = re.search(r"ALL_CRATES = (\[[^\]]*\])", crates_js)
    return [str(name) for name in json.loads(match.group(1))] if match else []


def rustdoc_files(doc: Path, libraries: tuple[str, ...]) -> Iterator[Path]:
    """The rustdoc output the site serves.

    That is the libraries' pages, their sources and the shared files (styles, search, the
    implementor lists), leaving out any other crate's pages that a `cargo doc` with
    dependencies may have left behind.

    Yields:
        Each file to copy, in a stable order.
    """
    for path in sorted(doc.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(doc).parts
        top = parts[0]
        if top.startswith("."):
            continue
        if (doc / top / "all.html").exists() and top not in libraries:
            continue
        if top == "src" and len(parts) > 1 and parts[1] not in libraries:
            continue
        yield path


def write_python_reference(open_file: Opener) -> None:
    """One page per module, and the SUMMARY.md literate-nav reads for the section's nav."""
    summary = ["* [Overview](index.md)"]
    overview = [
        "# SDK reference",
        "",
        "Generated by mkdocstrings from the docstrings on every build. The SDK is what a plugin",
        "imports; the example plugins show it in use.",
    ]
    for title, root in PYTHON_ROOTS:
        packages = sdk_packages(root) if title == "The SDK" else plugin_packages(root)
        summary.append(f"* {title}")
        overview += ["", f"## {title}", ""]
        for package in packages:
            for name in python_modules(package):
                page = f"{name.replace('.', '/')}.md"
                with open_file(f"reference/python/{page}", "w") as handle:
                    handle.write(module_page(name))
                # Python-Markdown nests a list only at four spaces.
                summary.append(f"    * [`{name}`]({page})")
                if "." not in name:
                    overview.append(f"- [`{name}`]({page})")
    with open_file("reference/python/index.md", "w") as handle:
        handle.write("\n".join(overview) + "\n")
    with open_file("reference/python/SUMMARY.md", "w") as handle:
        handle.write("\n".join(summary) + "\n")


def write_rust(open_file: Opener) -> None:
    """Copy rustdoc's output into the site, then the crate overview and the API page."""
    doc = rustdoc_dir()
    built = {name for name in RUST_LIBRARIES if (doc / name / "index.html").exists()}
    if built:
        # rustdoc's crate list and search index would name these, and link to pages the
        # site leaves out.
        listed = rustdoc_crates((doc / "crates.js").read_text(encoding="utf-8"))
        if others := sorted(set(listed) - set(RUST_LIBRARIES)):
            LOG.warning(
                "%s also documents %s; scripts/docs.sh rebuilds it clean", doc, ", ".join(others)
            )
        for path in rustdoc_files(doc, RUST_LIBRARIES):
            with open_file(f"reference/rust/{path.relative_to(doc).as_posix()}", "wb") as handle:
                handle.write(path.read_bytes())
    crates = [crate_overview(path) for path in sorted((REPOSITORY / "crates").iterdir())]
    with open_file("core/crates.md", "w") as handle:
        handle.write(crates_page(crates, built))
    with open_file("core/rust-api.md", "w") as handle:
        handle.write(rust_api_page(built))


def write_cli(open_file: Opener) -> None:
    """The CLI page from the usage constants in cmd-host."""
    commands = []
    for title, source in (
        ("cmd plugin", "crates/cmd-host/src/cli.rs"),
        ("cmd plugin doctor", "crates/cmd-host/src/doctor.rs"),
    ):
        usage = rust_string_constant((REPOSITORY / source).read_text(encoding="utf-8"), "USAGE")
        if usage is None:
            # A USAGE built with concat! or format! is not a literal this can read.
            LOG.warning("%s has no USAGE string literal for the CLI page", source)
        else:
            commands.append((title, usage))
    with open_file("reference/cli.md", "w") as handle:
        handle.write(cli_page(commands))


def write_decisions(open_file: Opener) -> None:
    """One page per decision, an index, and the SUMMARY.md for the section's nav."""
    items = sorted(
        (decision(path) for path in (REPOSITORY / "backlog" / "decisions").glob("decision-*.md")),
        key=decision_number,
    )
    for item in items:
        with open_file(f"core/decisions/{item.id}.md", "w") as handle:
            handle.write(decision_page(item))
    with open_file("core/decisions/index.md", "w") as handle:
        handle.write(decisions_index(items))
    summary = ["* [All decisions](index.md)", *(f"* [{d.title}]({d.id}.md)" for d in items)]
    with open_file("core/decisions/SUMMARY.md", "w") as handle:
        handle.write("\n".join(summary) + "\n")


def write_catalogue(open_file: Opener) -> None:
    """The users' catalogue and the authors' examples, from the same reading of the index."""
    listed = listed_plugins(REPOSITORY)
    with open_file("use/catalogue.md", "w") as handle:
        handle.write(catalogue_page(listed))
    with open_file("plugins/examples.md", "w") as handle:
        handle.write(examples_page(listed))


def main() -> None:
    """Write every generated page through mkdocs-gen-files' virtual file system."""
    gen_files = importlib.import_module("mkdocs_gen_files")
    open_file: Opener = gen_files.open
    write_python_reference(open_file)
    write_rust(open_file)
    write_cli(open_file)
    write_decisions(open_file)
    write_catalogue(open_file)


if __name__ == "<run_path>":  # how mkdocs-gen-files runs a script
    main()
