---
id: TASK-8
title: The window shows running and failed plugin tasks in the status line
status: To Do
assignee: []
created_date: '2026-10-10 18:30'
updated_date: '2026-10-14 19:13'
labels:
  - size-3
milestone: m-3
dependencies:
  - TASK-7
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 12. Shares the status line with start trouble (TASK-1.39). Running tasks show label and done/total; done shows for a few seconds; failed stays until dismissed. Redraw at most every 250 ms. Depends on the protocol task.
<!-- SECTION:DESCRIPTION:END -->
