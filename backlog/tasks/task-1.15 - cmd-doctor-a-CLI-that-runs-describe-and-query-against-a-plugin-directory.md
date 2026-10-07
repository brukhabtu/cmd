---
id: TASK-1.15
title: 'cmd doctor: a CLI that runs describe and query against a plugin directory'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:31'
labels:
  - size-3
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 16000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cmd doctor <dir> prints the description, the items for a given query, and the effect for a given item, exactly as the host sees them
- [ ] #2 A plugin that writes to stdout outside the protocol is diagnosed with the offending line
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. A cmd-doctor binary in cmd-host that loads a plugin directory's manifest, starts the process, prints the description, then the items for --query and the effect for --run, exactly as the host sees them.
2. Protocol problems (stray stdout, timeouts, errors) print the host's own message and exit 1.
3. Tests run the built binary against the calculator and against a fake that chatters on stdout.
### Risks
None beyond argument parsing by hand; no new dependencies.
### Proof
cargo test -p cmd-host --test doctor.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented: cmd-doctor (crates/cmd-host/src/bin/cmd-doctor.rs) loads a plugin directory, prints the manifest and description, then the items for --query and the effect for --run, as JSON; protocol problems print the host's own message and exit 1, usage mistakes exit 2. Tests drive the built binary against the calculator and against a fake that chatters on stdout. Awaiting review.
<!-- SECTION:NOTES:END -->
