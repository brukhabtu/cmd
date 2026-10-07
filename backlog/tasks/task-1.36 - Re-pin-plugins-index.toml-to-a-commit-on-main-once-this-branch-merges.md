---
id: TASK-1.36
title: Re-pin plugins/index.toml to a commit on main once this branch merges
status: To Do
assignee: []
created_date: '2026-10-07 05:32'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The two entries pin commit 1159f73, which is only on ccr-16512bde-x72oqp. A squash merge that deletes the branch makes it unreachable, GitHub stops serving it by hash, and the index check and every install of those entries fail with no change to the file. After the merge, move both refs to a commit on main (or a tag) and keep the header's rule: refs stay reachable from something that lasts. From the review of 1.35.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Both entries point at a commit reachable from main or a tag, and scripts/check_index.py passes against GitHub
<!-- AC:END -->
