---
id: TASK-1.38
title: Icons on the files plugin's rows
status: Done
assignee: []
created_date: '2026-10-07 07:22'
updated_date: '2026-10-07 10:53'
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
- [x] #1 A files row carries the path icon and the adapter test asserts it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The plugin side landed with task 1.24 (search.py gives each row icon=PathIcon(path), and test_search.py asserts it). What was missing for the criterion: the Rust adapter test did not assert it. crates/cmd-host/tests/files.rs now asserts every row's icon is Icon::Path of the path it opens; with the plugin's icon line set to None the test fails (0 passed, 1 failed), restored it passes. Awaiting review.

Closed on the reviewer's verdict (CLOSE) against 2f9f070: the row carries icon=PathIcon(path) and the adapter test asserts it for both rows, tied to each row's own id.
<!-- SECTION:NOTES:END -->
