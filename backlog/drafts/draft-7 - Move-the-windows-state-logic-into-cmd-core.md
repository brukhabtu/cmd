---
id: DRAFT-7
title: Move the window's state logic into cmd-core
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies: []
parent_task_id: TASK-2
type: task
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
About 150 lines in crates/cmd-app/src/main.rs decide things: the plugins still starting, start trouble shown again on each show, the 300 ms waiting-on logic with Instant, re-asking for text typed before the host arrived, and the HostEvent to Event mapping. cmd-app does not build on Linux, so none of it is tested. Pass time in as an event.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Those decisions are Events and Steps in cmd-core with tests, and cmd-app only performs and draws
- [ ] #2 The window behaves as before on a Mac
<!-- AC:END -->
