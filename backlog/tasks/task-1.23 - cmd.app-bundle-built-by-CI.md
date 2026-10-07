---
id: TASK-1.23
title: cmd.app bundle built by CI
status: To Do
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 02:43'
labels:
  - size-5
milestone: m-3
dependencies:
  - TASK-1.22
parent_task_id: TASK-1
type: task
ordinal: 24000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cargo-bundle or an equivalent produces cmd.app with an icon and an Info.plist that hides the Dock icon
- [ ] #2 The macOS CI job uploads the bundle as an artifact on every push to main
<!-- AC:END -->
