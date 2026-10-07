---
id: TASK-1.30
title: Show plugin start failures in the window
status: To Do
assignee: []
created_date: '2026-10-07 04:44'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
start_host prints StartErrors to stderr; the person at the window never sees them (review of task 1.18).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin that fails to start at launch is named in a line under the input on first show, not only on stderr
<!-- AC:END -->
