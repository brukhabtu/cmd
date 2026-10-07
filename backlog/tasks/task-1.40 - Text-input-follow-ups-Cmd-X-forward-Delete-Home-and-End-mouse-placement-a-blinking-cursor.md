---
id: TASK-1.40
title: >-
  Text input follow-ups: Cmd-X, forward Delete, Home and End, mouse placement, a
  blinking cursor
status: To Do
assignee: []
created_date: '2026-10-07 11:00'
updated_date: '2026-10-07 11:54'
labels:
  - size-2
milestone: m-2
dependencies:
  - TASK-1.10
parent_task_id: TASK-1
type: task
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Task 1.10 built the query line on cmd_core::input::Input with Backspace and its chords, the arrows, Cmd-A, Cmd-C, Cmd-V and the input method. Left out by its plan: Cmd-X (copy then delete the selection), forward Delete and Option-Delete (Motion::NextGrapheme and NextWord already exist in cmd-core), Home and End and Ctrl-A and Ctrl-E, placing the cursor and selecting with the mouse (character_index_for_point already answers), and a blinking cursor. Each is a row in decision 4's key table and an Event in cmd-core.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Cmd-X, forward Delete, Option-Delete, Home and End do what a Cocoa text field does, each a row in decision 4
- [ ] #2 A click places the cursor and a drag selects, through the state machine
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A build was started at 11:53 and stopped unreviewed at 11:56 when the run wound down; nothing from it was merged. Next session: criterion 1 (Cmd-X, forward Delete, Option-Delete, Home, End, Ctrl-A, Ctrl-E) first, read gpui's key names from its source; criterion 2 (mouse) as its own slice.
<!-- SECTION:NOTES:END -->
