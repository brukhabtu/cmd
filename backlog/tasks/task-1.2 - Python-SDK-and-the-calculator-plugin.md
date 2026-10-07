---
id: TASK-1.2
title: Python SDK and the calculator plugin
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
labels:
  - size-3
milestone: m-0
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 3000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cmd-sdk exposes Plugin, Item, Action, the Effect types and serve, with the core pure and the stdio loop thin
- [ ] #2 The calculator answers '2 + 2 * 3' with 8 through the real host, run by uv, in the adapter test
- [ ] #3 ruff, mypy strict and pytest are green, and the functional suite passes when run twice in one process
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built in the foundation session. Complete and checked by the author; awaiting close by a reviewer who did not do the work, from the acceptance criteria and the evidence in scripts/check.sh.
<!-- SECTION:NOTES:END -->
