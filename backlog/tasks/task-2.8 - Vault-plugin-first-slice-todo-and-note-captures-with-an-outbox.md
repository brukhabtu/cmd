---
id: TASK-2.8
title: 'Vault plugin, first slice: todo and note captures with an outbox'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-5
dependencies:
  - TASK-2.7
  - TASK-2.2
  - TASK-2.5
  - TASK-2.6
modified_files:
  - plugins/vault/cmd-plugin.toml
parent_task_id: TASK-2
type: task
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A new plugin under plugins/vault. Captures `todo` and `note` from config, written through the obsidian CLI in `run` only, with an outbox in the data directory so a capture made while Obsidian is closed or past the 10 s limit is kept and retried. `search` through the CLI with a 2 s deadline, only when Obsidian is running. Tested against a fake obsidian executable whose path is configurable. The real CLI check is owed on a Mac.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 todo and note captures are written to the configured target through the CLI, from config alone
- [ ] #2 With the fake CLI closed, slow or failing, the capture stays in the outbox and is written once when it recovers
- [ ] #3 query never raises, never calls the CLI while Obsidian is not running, and returns within the host timeout
- [ ] #4 The check owed on a Mac is recorded on this task
<!-- AC:END -->
