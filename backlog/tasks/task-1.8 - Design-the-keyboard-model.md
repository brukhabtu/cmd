---
id: TASK-1.8
title: 'Design: the keyboard model'
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:34'
labels:
  - size-1
milestone: m-1
dependencies: []
parent_task_id: TASK-1
type: design
ordinal: 9000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A decision records which keys the app owns (Escape, arrows, Enter, Cmd-number, Cmd-K) and which reach plugins as text, including modifiers and IME input
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. List the keys the launcher must own and the ones that must reach plugins as text.
2. Write the decision, including modifiers and IME, and point the state machine's Event enum at it.
### Risks
IME behaviour can only be checked on a Mac.
### Proof
A decision record; the key mapping in cmd-app matches it.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Decision 4 on the board is the key table. cmd-core gained Clear and Pick(n) with tests; crates/cmd-app/src/main.rs maps keys exactly as the table says. Awaiting review.

Review fix: decision 4 now owns Cmd-K (reserved for the actions menu protocol v1 needs, dropped until then) and says an owned key answers with or without a modifier, which is what on_key does; the Cmd-number consequence is corrected.

Closed by the close-out reviewer on the second pass: decision 4 has the Cmd-K row, the modifier sentence matches on_key, and the Cmd-number consequence is corrected.
<!-- SECTION:NOTES:END -->
