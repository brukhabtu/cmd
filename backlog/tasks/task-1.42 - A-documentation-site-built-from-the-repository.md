---
id: TASK-1.42
title: A documentation site built from the repository
status: In Progress
assignee: []
created_date: '2026-10-07 12:14'
updated_date: '2026-10-07 12:14'
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
- [ ] #1 scripts/docs.sh builds the site with mkdocs build --strict and scripts/check.sh runs it, so a broken link or a missing reference fails CI; CI uploads the built site as an artifact
- [ ] #2 The Python SDK and the Rust crates' API references, the plugin catalogue, the decisions and the CLI usage are generated from the repository on every build, not written by hand
- [ ] #3 The landing page leads to three sections (using cmd, writing plugins, working on the core), and the user section shows the app in screenshots
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
