---
id: TASK-1.5
title: Architecture as orthodox C4 in LikeC4
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:51'
labels:
  - size-1
milestone: m-0
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 6000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 npx likec4 validate and c4lint pass on docs/architecture
- [x] #2 docs/architecture.md explains the shapes and where each boundary is enforced
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built in the foundation session. Complete and checked by the author; awaiting close by a reviewer who did not do the work, from the acceptance criteria and the evidence in scripts/check.sh.

Closed by the close-out reviewer. Its follow-ups were applied: the enforcement table in docs/architecture.md now says what is mechanical (clippy.toml forbids I/O in cmd-core; pypeeker gates protocol never importing serve) and what is by review; npx likec4 validate runs in scripts/check.sh.
<!-- SECTION:NOTES:END -->
