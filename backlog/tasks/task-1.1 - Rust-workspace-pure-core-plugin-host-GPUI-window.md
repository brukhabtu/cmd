---
id: TASK-1.1
title: 'Rust workspace: pure core, plugin host, GPUI window'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
labels:
  - size-5
milestone: m-0
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 2000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cmd-core has no I/O dependencies and its unit tests cover routing, merging and the launcher state machine
- [ ] #2 cmd-host runs a plugin as a process with per-call timeouts; the fake-plugin suite covers describe, timeout, late answers, stray stdout, plugin errors and exit
- [ ] #3 cmd-app compiles against gpui 0.2 on macOS CI (on Linux, the xattr/libc clash below GPUI is documented)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built in the foundation session. Complete and checked by the author; awaiting close by a reviewer who did not do the work, from the acceptance criteria and the evidence in scripts/check.sh.
<!-- SECTION:NOTES:END -->
