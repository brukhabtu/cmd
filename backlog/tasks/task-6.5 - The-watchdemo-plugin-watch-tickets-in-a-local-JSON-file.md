---
id: TASK-6.5
title: 'The watchdemo plugin: watch tickets in a local JSON file'
status: To Do
assignee: []
created_date: '2026-10-14 18:32'
updated_date: '2026-10-14 19:13'
labels:
  - size-3
milestone: m-3
dependencies:
  - TASK-6.2
  - TASK-6.3
parent_task_id: TASK-6
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 13. plugins/watchdemo: tickets (id, title, status) from a file named in config. Rows with complete; actions Open, Watch, Unwatch; a watching verb; a polling thread diffing the watched tickets against the stored state in CMD_PLUGIN_DATA; notify on a changed status, one summary after a wake with many; a decision-12 task when the file is unreadable; home rows for what moved (DRAFT-5). Pure core plus shell; tests mutate the file; pypeeker table rows; index entry; user page. No network and no credential.
<!-- SECTION:DESCRIPTION:END -->
