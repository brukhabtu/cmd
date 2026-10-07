---
id: TASK-1.14
title: >-
  Restart a crashed plugin, reload a changed one, show plugin errors in the
  window
status: To Do
assignee: []
created_date: '2026-10-07 02:40'
labels:
  - size-3
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 15000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin that exits is restarted on the next query, with back-off and a visible notice
- [ ] #2 Editing a plugin's files or manifest reloads it without restarting the app
- [ ] #3 Errors from a plugin appear as a one-line message under the input and clear when the text changes
<!-- AC:END -->
