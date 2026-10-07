---
id: TASK-1.35
title: plugins/index.toml and its CI check
status: To Do
assignee: []
created_date: '2026-10-07 05:24'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 8. The index lists plugins by name with summary, source (git URL), ref (tag or commit) and optional subdirectory, and lists this repository's own plugins by subdirectory. CI checks the shape, that names are unique and match the manifest at the ref, and resolves every tag to the commit it points at, storing the commit beside it, since a tag can be moved after review.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The index lists calculator and websearch by subdirectory at a commit of this repository
- [ ] #2 CI fails on a malformed entry, a duplicate name, a missing ref, or a tag the check cannot resolve, and records each tag's commit
<!-- AC:END -->
