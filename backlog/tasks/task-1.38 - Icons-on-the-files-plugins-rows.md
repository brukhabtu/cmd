---
id: TASK-1.38
title: Icons on the files plugin's rows
status: To Do
assignee: []
created_date: '2026-10-07 07:22'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Once protocol 1 (task 1.24) lands, each files row carries icon = PathIcon(path) so the row shows the file's own icon. One line in plugins/files/src/files/search.py plus a test line. From the scheduling of wave 1, where 1.20 landed before 1.24.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A files row carries the path icon and the adapter test asserts it
<!-- AC:END -->
