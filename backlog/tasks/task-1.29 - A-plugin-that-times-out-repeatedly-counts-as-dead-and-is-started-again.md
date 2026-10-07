---
id: TASK-1.29
title: A plugin that times out repeatedly counts as dead and is started again
status: To Do
assignee: []
created_date: '2026-10-07 04:44'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today is_gone covers exit and broken pipes only, so a wedged plugin costs a timeout per query forever (review of task 1.14).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After N consecutive timeouts (N configured in Timeouts) the worker kills and restarts the process, with the same back-off and notice as a crash
<!-- AC:END -->
