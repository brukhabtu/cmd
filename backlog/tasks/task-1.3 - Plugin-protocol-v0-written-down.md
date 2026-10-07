---
id: TASK-1.3
title: Plugin protocol v0 written down
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:55'
labels:
  - size-2
milestone: m-0
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 4000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 docs/plugin-protocol.md covers the manifest, transport, methods, shapes, routing, ranking, timeouts, lifecycle and errors
- [x] #2 The Rust side and the Python side match the document, proven by the adapter test
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built in the foundation session. Complete and checked by the author; awaiting close by a reviewer who did not do the work, from the acceptance criteria and the evidence in scripts/check.sh.

Close-out review kept this open: the Errors section promised the host shows the plugin's message and the host did not. The host now does, and the section states that an id-0 error answers the request in flight. Ready for re-review.

Closed by the close-out reviewer on re-review at bb92a89: the Errors section and the host agree, and the fake-plugin suite covers both error behaviours. Noted for later: the calculator adapter test covers only the happy path; error shapes are proven through the fake plugin, not the real SDK.
<!-- SECTION:NOTES:END -->
