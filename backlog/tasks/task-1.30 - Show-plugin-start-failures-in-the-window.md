---
id: TASK-1.30
title: Show plugin start failures in the window
status: In Progress
assignee: []
created_date: '2026-10-07 04:44'
updated_date: '2026-10-07 04:59'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
start_host prints StartErrors to stderr; the person at the window never sees them (review of task 1.18).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin that fails to start at launch is named in a line under the input on first show, not only on stderr
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. start_host hands the StartErrors to the view; the view shows them as the message on the first render.
### Proof
Clippy in the scratch workspace; the line appears on a Mac.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: start_host returns the host beside every message it printed (manifest load errors, 'no plugins found in ...', start errors); LauncherView::new applies them as one Noted line, so the first render shows them under the input. Clippy passes in the scratch workspace; not yet seen on a Mac. Awaiting review.
<!-- SECTION:NOTES:END -->
