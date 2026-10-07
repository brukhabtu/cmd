---
id: TASK-1.10
title: 'A real text input: cursor, selection, paste, word deletion'
status: To Do
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:43'
labels:
  - size-5
milestone: m-1
dependencies:
  - TASK-1.8
parent_task_id: TASK-1
type: task
ordinal: 11000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Left and right move the cursor; Shift extends a selection; Cmd-A, Cmd-C, Cmd-V and Cmd-Backspace do what macOS does
- [ ] #2 IME composition (for example Japanese input) works, verified by hand on macOS
- [ ] #3 The state machine in cmd-core stays the only owner of the text; the view renders it
<!-- AC:END -->
