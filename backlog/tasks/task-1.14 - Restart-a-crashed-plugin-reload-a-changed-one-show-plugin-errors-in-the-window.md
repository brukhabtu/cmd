---
id: TASK-1.14
title: >-
  Restart a crashed plugin, reload a changed one, show plugin errors in the
  window
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:44'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Worker: when a call says the process is gone (exited, broken pipe), answer the current command with that error, restart the plugin with back-off (2 s doubling to 30 s, reset after a healthy call), and report a Restarted event the window shows as a notice.
2. Core: a Noted event that shows a line regardless of generation.
3. Test with the fake that exits on 'quit': the next query is answered by the fresh process.
4. Reload on file change is not in this slice; it stays on the task.
### Risks
A plugin that dies on every query restarts forever at the capped delay; the notice makes that visible.
### Proof
cargo test -p cmd-host --test host.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
First slice landed: a plugin whose process has gone (exited, broken pipe) gets its command answered with that fact, is started again with back-off (2 s doubling to 30 s, reset after a healthy call), and the window shows '<plugin> started again (restart n)'. Test a_plugin_that_exits_is_started_again_for_the_next_query. Not done: reload when a plugin's files change (the second criterion). The third criterion (errors as a line under the input, cleared when the text changes) is how Unanswered and Failed already render.

Second slice: a change to any file under the plugin's directory (hidden directories and __pycache__ excepted) reloads it on the new code, with a 200 ms settle and collapsing of bursts; test a_changed_file_reloads_the_plugin_onto_the_new_code rewrites the fake and sees the new name answer. From the review: a failed restart or reload is now reported in the window (HostEvent::Trouble); Restarts::delay has a unit test; the Lifecycle section of docs/plugin-protocol.md is current. Not done, as tasks: a hung plugin counting as dead; start failures in the window. Awaiting review.
<!-- SECTION:NOTES:END -->
