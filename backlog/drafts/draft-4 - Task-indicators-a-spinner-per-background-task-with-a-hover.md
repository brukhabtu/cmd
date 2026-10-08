---
id: DRAFT-4
title: 'Task indicators: a spinner per background task, with a hover'
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-8
dependencies: []
parent_task_id: TASK-2
type: design
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DEFERRED by the owner (2026-10-08). Not accepted; split before committing, as it is size 8.

A small spinner in the top right of the window per running task, hover for what it is doing. Two sources: calls the host already has in flight past 300 ms, and work a plugin does between calls (the outbox retrying, a cache refresh). The second needs a plugin-to-host event, which needs the capability negotiation from TASK-2.3 and a host reader that handles id-less lines between calls, and an SDK that serialises stdout writes from a background thread. A task is {id, label, detail, state: running|done|failed}. A restart clears that plugin's tasks. The host's own start-up work (starting plugins, fetching Python, restart back-off) becomes tasks, replacing the status-line special cases of TASK-1.30 and TASK-1.39. Animate only while a task exists.

**Decided: failed tasks persist until dismissed**, since a capture lost in the background is the worst outcome here. Open: a macOS notification for a failure while the window is hidden (a new effect, so a protocol bump), and a menu bar item to show the spinner while hidden. Neither is in scope for a first cut.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A task a plugin reports shows as a spinner with its plugin, label, detail and elapsed time on hover
- [ ] #2 A failed task stays until dismissed and shows on the next open
- [ ] #3 A plugin restart clears its tasks, and an old host never receives an event it cannot decode
<!-- AC:END -->
