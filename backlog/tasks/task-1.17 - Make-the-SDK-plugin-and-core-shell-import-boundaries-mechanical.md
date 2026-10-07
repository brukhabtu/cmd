---
id: TASK-1.17
title: Make the SDK/plugin and core/shell import boundaries mechanical
status: To Do
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:51'
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
- [ ] #1 pypeeker check --strict (or its replacement) fails when cmd_sdk imports a plugin or a plugin imports another plugin, and passes on main
- [ ] #2 The existing gate for the core/shell line inside cmd_sdk keeps passing and stays in scripts/check.sh
<!-- AC:END -->
