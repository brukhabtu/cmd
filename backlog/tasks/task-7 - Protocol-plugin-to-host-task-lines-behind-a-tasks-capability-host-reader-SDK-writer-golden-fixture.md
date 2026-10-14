---
id: TASK-7
title: >-
  Protocol: plugin-to-host task lines, behind a tasks capability (host reader,
  SDK writer, golden fixture)
status: Done
assignee: []
created_date: '2026-10-10 18:30'
updated_date: '2026-10-14 19:35'
labels:
  - size-5
milestone: m-3
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 12. The host's reader thread classifies each line as it arrives (event vs response); HostEvent::Task; the latest state per task per plugin; a malformed line is trouble, never a failed call. The SDK gets report() callable from any thread under serve's write lock, a throttle, and checks of the task shape. The host names tasks in capabilities. Rust side, Python side, docs/plugin-protocol.md, the golden fixture and the adapter test change together. Amend decision 9's third kind.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: closed on review by a read-only reviewer who did not do the work (no blocking findings). Non-blocking, filed as a draft: a line buffered by a dead process can put a stale task back before Restarted (retire the old token in clear()); the reader parses each line twice and read_line is unbounded.
<!-- SECTION:NOTES:END -->
