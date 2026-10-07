---
id: TASK-1.7
title: 'Spike: a global hotkey for a GPUI app on macOS'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 03:37'
labels:
  - size-3
milestone: m-1
dependencies: []
parent_task_id: TASK-1
type: spike
ordinal: 8000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision on the board names the mechanism (global-hotkey crate, CGEventTap, or an NSEvent global monitor), the permissions it needs, and how it coexists with Spotlight's own Cmd-Space
- [ ] #2 A demo binary shows and hides a GPUI window on the hotkey
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Read the global-hotkey crate's macOS backend and GPUI's run loop to decide how a hotkey event reaches the App.
2. Write the decision: mechanism, permissions, Spotlight coexistence, and the integration shape.
3. The demo is cmd-app itself (task 1.9 builds on this spike); macOS CI compiles it, a person runs it.
### Risks
No Mac in this environment: behaviour is verified by compile on macOS CI and by reading sources, not by pressing the key.
### Proof
A decision record on the board; cmd-app compiles on macOS CI with the hotkey wired.
<!-- SECTION:PLAN:END -->
