---
id: DRAFT-9
title: 'Design: frecency ranking'
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies: []
parent_task_id: TASK-2
type: design
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The core knows which plugin and item were run, so the host can store usage and the merge can use it. Problem to settle: items without a score always rank above scored ones, so usage can never lift a fuzzy match past a definite answer. Decide where the usage lives and how a boost combines with score.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision records the store, the boost and how it ranks against unscored items
<!-- AC:END -->
