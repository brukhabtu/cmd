---
id: TASK-9
title: The vault reports its outbox as tasks
status: Done
assignee: []
created_date: '2026-10-10 18:30'
updated_date: '2026-10-14 19:48'
labels:
  - size-2
milestone: m-3
dependencies:
  - TASK-7
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 12. Running with done and total while captures are written or retried; failed on one it cannot write. Depends on the protocol task.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: closed on review by a read-only reviewer who did not do the work (181 vault tests pass, no blocking findings). Owed on the Mac with a real Obsidian: the same checklist as TASK-2.8 plus the status line showing the outbox.
<!-- SECTION:NOTES:END -->
