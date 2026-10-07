---
id: TASK-1.1
title: 'Rust workspace: pure core, plugin host, GPUI window'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:51'
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

Close-out review kept this open: the late-answer test did not test a late answer (the fake now answers after 300 ms and the host skips the stale id), plugin error messages were swallowed by DecodeError::Plugin's display (now 'the plugin reported an error: code: message'), an id-0 error was skipped as stale (now answers the request in flight), the manifest doc comment showed the wrong command (fixed), and the scratch workspace used for the Linux compile check had drifted (re-synced; cargo clippy -p cmd-app -D warnings rehearsed there). Still waiting on: the macOS CI job on the pushed branch.
<!-- SECTION:NOTES:END -->
