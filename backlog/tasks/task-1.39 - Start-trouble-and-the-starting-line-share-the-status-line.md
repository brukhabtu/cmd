---
id: TASK-1.39
title: Start trouble and the starting line share the status line
status: To Do
assignee: []
created_date: '2026-10-07 11:13'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the review of 1.32: status_line shows state.message (start trouble, in the warning colour) before waiting_on (the 'starting a, b' line), so one plugin failing at launch hides which plugins are still starting until a key is pressed. Show both: the trouble line and, beneath or after it, the starting line, or fold the starting names into the trouble line while any remain.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With one plugin failing and another still starting, the window shows both the failure and the starting name
<!-- AC:END -->
