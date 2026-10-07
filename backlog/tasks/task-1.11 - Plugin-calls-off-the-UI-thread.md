---
id: TASK-1.11
title: Plugin calls off the UI thread
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:35'
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
- [x] #1 Typing never blocks on a plugin: queries run on a background executor and answers arrive as Results events with their generation
- [x] #2 A plugin that has not answered after 300 ms shows a quiet 'waiting on <plugin>' line
- [x] #3 The fake-plugin suite gains a case for an answer that arrives after a newer query was sent
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. cmd-core: replace the whole-list Results event with Asked, Answered and Unanswered per plugin; the launcher keeps the answers of the current generation and re-merges on each one; pending is the list still owed.
2. cmd-host: one worker thread per plugin owning its process; commands over std mpsc, events over an async-channel the app can await; a newer query supersedes a queued older one, a run is never skipped.
3. cmd-app: Step::Query asks and records who was asked; a foreground task turns host events into state events; a 300 ms timer re-renders so the waiting line can appear.
4. Tests: host functional suite with fast and slow fakes (ordering, stale skipping, run), the adapter test on the new API, core unit tests.
### Risks
The id-0 rule in the process layer assumes one request in flight per plugin, which one worker per plugin preserves. GPUI wiring is compile-checked, not run.
### Proof
cargo test green here; clippy green in the scratch workspace and on macOS CI.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented: cmd-core keeps per-plugin answers for the current generation (Asked, Answered, Unanswered events; pending is who still owes an answer); cmd-host runs one worker thread per plugin with commands over std mpsc and events over an async-channel, collapsing queued queries to the newest; cmd-app relays host events through a foreground task and shows 'waiting on <plugin>' after 300 ms. Host functional tests cover event delivery, a slow plugin delaying only itself, stale queries collapsing, run effects and error text; the adapter test runs on the new API. Clippy -D warnings green for cmd-app in the scratch workspace. Awaiting macOS CI and review.

CI run 9 (cbe7b68) green on both jobs. Review fixes: runs carry the generation they were issued in and a run whose effect arrives after Escape or more typing is dropped (core test a_run_that_finishes_after_escape_or_more_typing_is_dropped); Enter while a run is in flight does nothing (busy flag, test enter_twice_runs_once_until_the_run_finishes); plugin names are added to error text once, in the app; the host suite has a deterministic case where an answer arrives after a newer query was sent; the misnamed test is renamed.

Closed by the close-out reviewer on the second pass, with CI run 11 (https://github.com/brukhabtu/cmd/actions/runs/37571889213, e435201) green on both jobs. Known edge the reviewer noted: after a query timeout, an id-0 error from the old request can be attributed to the next one; pre-existing, on the process layer.
<!-- SECTION:NOTES:END -->
