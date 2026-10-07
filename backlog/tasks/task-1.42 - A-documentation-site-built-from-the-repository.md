---
id: TASK-1.42
title: A documentation site built from the repository
status: Done
assignee: []
created_date: '2026-10-07 12:14'
updated_date: '2026-10-07 12:53'
labels:
  - size-3
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
MkDocs (Material) at the repository root, built by scripts/docs.sh and checked by scripts/check.sh, with three audiences: people using the app, Python plugin authors, and core (Rust) contributors. This task builds the structure and the generation; the writing is the documentation epic (TASK-1.43). Generated from code on every build: the Python SDK's API reference (mkdocstrings), the Rust crates' API reference (rustdoc) and an overview from their module docs, the plugin catalogue from plugins/index.toml and the manifests, the decisions from backlog/decisions, and the CLI usage from the binaries' own usage text. Hand-written for now: the landing page and short user pages with screenshots; everything else is a placeholder that says what will go there.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scripts/docs.sh builds the site with mkdocs build --strict and scripts/check.sh runs it, so a broken link or a missing reference fails CI; CI uploads the built site as an artifact
- [x] #2 The Python SDK and the Rust crates' API references, the plugin catalogue, the decisions and the CLI usage are generated from the repository on every build, not written by hand
- [x] #3 The landing page leads to three sections (using cmd, writing plugins, working on the core), and the user section shows the app in screenshots
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. A docs dependency group (mkdocs-material, mkdocstrings[python], mkdocs-gen-files, mkdocs-literate-nav) and mkdocs.yml at the root, docs_dir docs/ so the existing pages keep their paths.
2. docs/gen/*.py run by mkdocs-gen-files: Python API pages per module, the plugin catalogue, the decisions, the CLI usage, and a Rust crate overview from the //! docs.
3. scripts/docs.sh: cargo doc for the library crates into a gitignored folder the site serves, then mkdocs build --strict. scripts/check.sh runs it; CI uploads site/.
4. The landing page and the user pages with screenshots (taken by a separate agent under Xvfb from the Linux build); placeholders elsewhere.
### Proof
scripts/check.sh green with the docs step; the built site browsed locally.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Progress, 2026-10-07:
- The site builds strict and scripts/check.sh runs it. CI uploads site/ as the docs-site artifact, built with MKDOCS_DIRECTORY_URLS=false so the download browses from disk.
- Screenshots: launcher-empty, calculator, websearch and system, plus launcher-starting under Everyday use's line under the input. scripts/screenshots.sh takes them from cmd-app's Linux build under Xvfb, in the workspace scripts/linux-app-workspace.sh makes; two runs gave byte-identical files. They are Linux renderings (a flat grey for the translucent tint, DejaVu Sans, the light palette, no icons since those come from AppKit), and Using cmd says so in a note.
- Found while publishing a private preview: rustdoc's crate list and search index named cmd_plugin (cmd-host's binary), whose pages the site leaves out, and rustdoc merges those files into whatever an earlier run left in target/doc. docs.sh now runs cargo clean --doc and cargo doc --lib; docs_gen warns, which fails --strict, when crates.js lists another crate.
- Found by check.sh: ruff format now formats the Python in Markdown code blocks. The example on plugins/index.md failed it, which turned CI red on 1ee27f9 and ba80666.
- The preview left out what its host does not serve or an English site never loads: objects.inv, sitemap.xml.gz, the source maps and lunr's other-language packs. TASK-1.44 picks the real host.

Review at close, 2026-10-07: a read-only reviewer who did not do the work checked ce26af8 and said close, with all three criteria met (docs.sh run strict, the generator tests, check.sh and ci.yml read, the pages and screenshots looked at; CI run 58 green with the docs-site artifact). Its findings, and what became of them:
- Should fix, fixed: the keys table left out the option and cmd arrow moves and called cmd+backspace clearing the input, when it deletes to the line start (crates/cmd-app/src/main.rs).
- Should fix, fixed: Keywords left out the applications plugin, which answers part of an app's name without one.
- Nit, fixed: plugins.md shows update with a name.
- Nit, fixed: the CLI page reads the USAGE string literals, and a USAGE built with concat! or format! would have dropped its command silently; docs_gen now warns, which fails the strict build.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Closed on review at close: all three criteria met. scripts/docs.sh builds the site with mkdocs build --strict, scripts/check.sh runs it, and CI uploads the result as the docs-site artifact. Generated from the repository on every build: the Python API pages for the SDK and the example plugins, the Rust API reference and crate overview, the CLI usage, the decisions, and the plugin catalogue and examples. The landing page leads to using cmd, writing plugins and working on the core, and the user pages show five screenshots of the real app. The writing is TASK-1.43 and hosting the site is TASK-1.44.
<!-- SECTION:FINAL_SUMMARY:END -->
