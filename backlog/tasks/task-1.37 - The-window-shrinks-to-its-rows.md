---
id: TASK-1.37
title: The window shrinks to its rows
status: To Do
assignee: []
created_date: '2026-10-07 07:22'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The launcher window is a fixed 420 px tall, so a short list leaves an empty translucent area under the rows. Resize the window to the input plus the rows on screen on every answer (gpui Window::resize), keeping the top edge where it is. Left out of 1.12 on purpose.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With two results the window is the input, the status line and two rows tall; with ten it shows seven and scrolls
<!-- AC:END -->
