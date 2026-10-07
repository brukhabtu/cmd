---
id: TASK-1.27
title: Place the launcher on the active display
status: To Do
assignee: []
created_date: '2026-10-07 04:34'
labels:
  - size-2
milestone: m-1
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today launcher_bounds in crates/cmd-app/src/main.rs positions the window on the primary display once at startup. GPUI offers cx.displays() and the active window's display; the show path should pick the display and recompute the bounds each time.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With several displays attached, the window shows on the display that holds the mouse pointer (or the active window), recomputed on every show
- [ ] #2 The bounds follow a changed display arrangement without restarting the app
<!-- AC:END -->
