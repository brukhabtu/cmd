---
id: TASK-1.17
title: Make the SDK/plugin and core/shell import boundaries mechanical
status: To Do
assignee: []
created_date: '2026-10-07 02:40'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 18000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 pypeeker check --strict fails when cmd_sdk imports a plugin or when cmd_sdk.protocol imports cmd_sdk.serve, and passes on main
- [ ] #2 scripts/check.sh runs it; the gap found in the foundation session (the rule could not see across the two source roots) is closed or the tool is replaced
<!-- AC:END -->
