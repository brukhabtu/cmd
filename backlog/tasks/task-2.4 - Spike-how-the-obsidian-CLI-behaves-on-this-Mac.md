---
id: TASK-2.4
title: 'Spike: how the obsidian CLI behaves on this Mac'
status: To Do
assignee:
  - '@brukhabtu'
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 20:34'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-08: cannot run in the cloud session the rest of TASK-2 is being built in (Linux, no Obsidian). It needs the owner's Mac with Obsidian 1.12.4 or later and the CLI on. TASK-2.7 (the vault design) and TASK-2.8 (the plugin) were done without it, as decision 9 allows: each says where a spike result would change a number or a branch, and 2.8 tests against a fake CLI. Running this spike closes the owed Mac check on TASK-2.8 as well.
From decision 10 (2026-10-08): add five questions to the spike. How does a call put a line under a heading in a note? Which command reads a note, and which reads today's daily note? Where is the CLI installed, as an absolute path a Dock launch can use? What does create do to a path that already exists? How does a call name its vault?
<!-- SECTION:NOTES:END -->
