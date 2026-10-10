---
id: DRAFT-15
title: >-
  Protocol: plugin-to-host task lines, behind a tasks capability (host reader,
  SDK writer, golden fixture)
status: Draft
assignee: []
created_date: '2026-10-10 18:30'
labels:
  - size-5
milestone: m-3
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 12. The host's reader thread classifies each line as it arrives (event vs response); HostEvent::Task; the latest state per task per plugin; a malformed line is trouble, never a failed call. The SDK gets report() callable from any thread under serve's write lock, a throttle, and checks of the task shape. The host names tasks in capabilities. Rust side, Python side, docs/plugin-protocol.md, the golden fixture and the adapter test change together. Amend decision 9's third kind.
<!-- SECTION:DESCRIPTION:END -->
