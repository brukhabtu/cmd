"""The documentation generators read the repository the way its files are written."""

import tomllib
from pathlib import Path

from docs_gen import (
    REPOSITORY,
    Decision,
    crate_overview,
    decision_number,
    decisions_index,
    declared_modules,
    description_keyword,
    front_matter,
    listed_plugins,
    module_docs,
    python_modules,
    rust_string_constant,
    rustdoc_crates,
)


def test_module_docs_are_the_leading_inner_comments_with_links_made_code() -> None:
    source = "//! The shell.\n//!\n//! [`Host`] owns plugins; see [the book](https://x).\n\nuse std::io;\n//! not docs\n"
    assert module_docs(source) == "The shell.\n\n`Host` owns plugins; see [the book](https://x)."
    assert not module_docs("use std::io;\n")


def test_declared_modules_are_read_in_order_public_or_not() -> None:
    source = "pub mod host;\nmod input;\n// mod commented;\npub use host::Host;\n"
    assert declared_modules(source) == ["host", "input"]


def test_a_rust_string_constant_is_read_with_its_escapes() -> None:
    source = 'const USAGE: &str = "usage: x <dir>\\n\\\n    second line with \\"quotes\\"";\n'
    assert rust_string_constant(source, "USAGE") == 'usage: x <dir>\nsecond line with "quotes"'
    assert rust_string_constant(source, "OTHER") is None


def test_rustdocs_crate_list_is_read_from_crates_js() -> None:
    text = 'window.ALL_CRATES = ["cmd_core","cmd_host","cmd_plugin"];\n//{"start":21}\n'
    assert rustdoc_crates(text) == ["cmd_core", "cmd_host", "cmd_plugin"]
    assert rustdoc_crates("") == []


def test_front_matter_reads_folded_titles_and_quoted_values() -> None:
    text = "---\nid: decision-7\ntitle: >-\n  cmd.app carries uv\n  and nothing else\ndate: '2026-10-07 05:25'\nstatus: proposed\n---\n## Context\n\nBody.\n"
    fields, body = front_matter(text)
    assert fields == {
        "id": "decision-7",
        "title": "cmd.app carries uv and nothing else",
        "date": "2026-10-07 05:25",
        "status": "proposed",
    }
    assert body == "## Context\n\nBody.\n"
    assert front_matter("no front matter") == ({}, "no front matter")


def test_decisions_are_ordered_by_number_and_indexed() -> None:
    items = [Decision(f"decision-{n}", f"Title {n}", "2026-10-07", "proposed", "") for n in (10, 2)]
    assert [decision_number(d) for d in sorted(items, key=decision_number)] == [2, 10]
    assert "| [decision-2](decision-2.md) | Title 2 | proposed | 2026-10-07 |" in decisions_index(
        items
    )


def test_a_keyword_is_read_from_the_description_call() -> None:
    assert (
        description_keyword('PLUGIN = Plugin(Description(name="w", keyword="web"), q, r)\n')
        == "web"
    )
    assert description_keyword('PLUGIN = Plugin(Description(name="c"), q, r)\n') is None


def test_python_modules_leave_out_private_ones(tmp_path: Path) -> None:
    package = tmp_path / "sdk"
    (package / "inner").mkdir(parents=True)
    for name in ("__init__.py", "protocol.py", "_private.py", "inner/__init__.py", "inner/deep.py"):
        (package / name).write_text("", encoding="utf-8")
    assert python_modules(package) == ["sdk", "sdk.inner.deep", "sdk.protocol"]


def test_the_catalogue_lists_every_plugin_the_index_lists_with_its_keyword() -> None:
    index = tomllib.loads((REPOSITORY / "plugins" / "index.toml").read_text(encoding="utf-8"))
    listed = listed_plugins(REPOSITORY)
    assert [item.name for item in listed] == [entry["name"] for entry in index["plugin"]]
    keywords = {item.name: item.keyword for item in listed}
    assert keywords["websearch"] == "web"
    assert keywords["calculator"] is None


def test_the_crates_and_the_cli_usage_are_found_in_the_repository() -> None:
    core = crate_overview(REPOSITORY / "crates" / "cmd-core")
    assert core.docs.startswith("The functional core of cmd.")
    assert "state" in dict(core.modules)
    cli = (REPOSITORY / "crates" / "cmd-host" / "src" / "cli.rs").read_text(encoding="utf-8")
    usage = rust_string_constant(cli, "USAGE")
    assert usage is not None
    assert usage.startswith("usage: cmd plugin <command>")
