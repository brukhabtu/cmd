---
id: TASK-1.17
title: Make the SDK/plugin and core/shell import boundaries mechanical
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 05:13'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pypeeker's import-boundaries rule, as pinned, derives units from each file's own top-level package, so it gates the core/shell line inside cmd_sdk (protocol may not import serve, already in scripts/check.sh) but cannot see an import that crosses the two source roots: cmd_sdk importing a plugin, or a plugin importing another plugin. Close the gap with a pypeeker root that spans both roots, a custom rule, or another tool.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 pypeeker check --strict (or its replacement) fails when cmd_sdk imports a plugin or a plugin imports another plugin, and passes on main
- [x] #2 The existing gate for the core/shell line inside cmd_sdk keeps passing and stays in scripts/check.sh
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. scripts/import_boundaries.py, stdlib only: for every module under the given source roots, read its absolute imports with ast; fail on cmd_sdk importing a package that lives under a plugin root, or a plugin package importing a sibling. Output path:line: <package> imports <package>; exit 1.
2. scripts/tests/test_import_boundaries.py: a clean tree, the SDK importing a plugin, a plugin importing another and itself, from-imports and relative imports, and the real tree.
3. A step in scripts/check.sh after pypeeker; docs/architecture.md's boundary table says the line is now mechanical.
### Risks
Only source roots are read, so a plugin's tests importing another plugin pass; nothing on the board needs that line.
### Proof
uv run pytest scripts/tests; scripts/check.sh; a deliberate crossing fails the step.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: scripts/import_boundaries.py (stdlib only) reads every absolute import under the source roots with ast and fails on cmd_sdk importing a plugin package or a plugin importing a sibling, printing path:line: <package> imports <package>; scripts/check.sh runs it after pypeeker, and pypeeker's core/shell gate inside the SDK stays as it was. Five tests in scripts/tests/test_import_boundaries.py (clean tree, SDK to plugin, plugin to sibling and to itself, nested modules and relative imports, the real tree). A deliberate 'import websearch' in the calculator fails the step with the file and line. docs/architecture.md's boundary table calls the line mechanical. Awaiting review.

Closed on the reviewer's verdict against 33ee847. Its two tidy-ups landed in the next commit: scripts/check.sh indexes every plugins/*/src for pypeeker (websearch was never indexed), and the [tool.pypeeker] comment in pyproject.toml points at scripts/import_boundaries.py. Limits accepted: packages without __init__.py and dynamic imports are invisible to the script; no plugin here has either.
<!-- SECTION:NOTES:END -->
