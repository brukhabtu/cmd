---
id: DRAFT-6
title: 'Cmd-K: an actions menu for an item'
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies: []
parent_task_id: TASK-2
type: task
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Enter and Cmd-n run only the first action; Cmd-K is dropped. websearch's "Copy the address" and files' OPEN cannot be reached from the window. The state belongs in cmd-core so it is tested on Linux. Wanted by the vault and feeds plugins for "copy id" and "append to the daily note".
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Cmd-K lists an item's actions, and Enter on one runs that action
- [ ] #2 The menu state is in cmd-core with tests
<!-- AC:END -->
