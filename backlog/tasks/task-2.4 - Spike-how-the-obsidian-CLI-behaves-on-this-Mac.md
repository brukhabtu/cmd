---
id: TASK-2.4
title: 'Spike: how the obsidian CLI behaves on this Mac'
status: To Do
assignee:
  - '@brukhabtu'
created_date: '2026-10-08 13:47'
labels:
  - size-2
dependencies: []
parent_task_id: TASK-2
type: spike
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Needs the Mac and Obsidian 1.12.4 or later with the CLI on. The riskiest assumption in the vault plugin is that the CLI answers well inside 2 s warm and fails fast and readably when Obsidian is closed or stuck.

Time 50 warm runs each of `search format=json`, `tasks format=json` and `append`; repeat with Obsidian quit and with it paused (kill -STOP). Record exit codes, stdout, stderr, and whether the app was launched. Also settle: does `create` accept both `content` and `template`; where a template-created file lands against `path=`; what `tasks format=json` returns (file and line, for toggling); whether `daily:append` creates the daily note.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A table of timings and outcomes for warm, closed and paused, with exit codes and output, is written into the vault design task
- [ ] #2 The four open behaviours (content with template, template path, tasks json fields, daily note creation) are answered
- [ ] #3 The intent's CLI-versus-files question is closed or carried forward on purpose
<!-- AC:END -->
