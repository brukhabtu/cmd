---
id: TASK-1.28
title: The host accepts protocol 0 and 1
status: To Do
assignee: []
created_date: '2026-10-07 04:44'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 6 promises compatibility across v0 and v1; the host currently refuses any version other than its own.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin describing itself as protocol 0 or 1 is loaded; any other version is refused with the message naming both
<!-- AC:END -->
