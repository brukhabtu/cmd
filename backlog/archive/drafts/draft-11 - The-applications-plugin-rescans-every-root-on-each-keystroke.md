---
id: DRAFT-11
title: The applications plugin rescans every root on each keystroke
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-1
dependencies: []
parent_task_id: TASK-2
type: bug
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
plugins/applications/src/applications/__init__.py:49. A module-level cache, refreshed on a timer or when a root changes, would do.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Typing does not rescan the application roots
<!-- AC:END -->
