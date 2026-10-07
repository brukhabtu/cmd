---
id: TASK-1.16
title: 'Design: protocol v1 candidates'
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:44'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: design
ordinal: 17000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A decision lists streaming results, icons, item detail panes and cancellation, with what each costs the SDK author, and picks what v1 carries
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. List what plugin authors and the window will ask of the protocol next, with the cost to an SDK author of each.
2. Record which of them v1 carries and which wait.
### Risks
Deciding before a second real plugin exists; the websearch plugin from task 1.18 is the second data point.
### Proof
A decision record on the board.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Decision 6 on the board: v1 adds optional icon and details fields on items and gives the existing actions list its window half (Cmd-K); streaming, cancellation and plugin-initiated updates wait, with the reasons. Awaiting review.

Closed by the close-out reviewer on the third pass. Its notes: how a details path is told apart from markdown is still to decide; 'the host accepts protocol 0 and 1' is now a board task.
<!-- SECTION:NOTES:END -->
