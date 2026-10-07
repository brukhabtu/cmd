---
id: TASK-1.11
title: Plugin calls off the UI thread
status: To Do
assignee: []
created_date: '2026-10-07 02:40'
labels:
  - size-3
milestone: m-1
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 12000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Typing never blocks on a plugin: queries run on a background executor and answers arrive as Results events with their generation
- [ ] #2 A plugin that has not answered after 300 ms shows a quiet 'waiting on <plugin>' line
- [ ] #3 The fake-plugin suite gains a case for an answer that arrives after a newer query was sent
<!-- AC:END -->
