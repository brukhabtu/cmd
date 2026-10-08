---
id: TASK-2.6
title: 'SDK helpers: data_dir, config, a call with a deadline, a TTL cache'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-2
dependencies:
  - TASK-2.5
modified_files:
  - python/cmd-sdk/src/cmd_sdk/__init__.py
parent_task_id: TASK-2
type: task
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Files and system each wrote their own subprocess call with a deadline. Move it to the SDK, with the other helpers every plugin in this intent needs: `data_dir()`, `config()` (TOML from the config path), a subprocess call that keeps partial output and leaves a slow child to finish, and a TTL cache with a background refresh thread. Files and system then use the shared call.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The helpers exist with tests, and files and system use the shared call
- [ ] #2 The SDK still imports no plugin and scripts/import_boundaries.py passes
<!-- AC:END -->
