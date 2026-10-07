---
id: TASK-1.29
title: A plugin that times out repeatedly counts as dead and is started again
status: In Progress
assignee: []
created_date: '2026-10-07 04:44'
updated_date: '2026-10-07 05:04'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today is_gone covers exit and broken pipes only, so a wedged plugin costs a timeout per query forever (review of task 1.14).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After N consecutive timeouts (N configured in Timeouts) the worker kills and restarts the process, with the same back-off and notice as a crash
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Timeouts gains hung_after: consecutive timeouts before the plugin counts as dead (default 3).
2. The worker counts timeouts in a row; at the limit it answers the call with 'did not answer n times in a row; starting it again', drops the process (which kills it) and restarts with the usual back-off and notice.
3. Test with the stalling fake and short timeouts.
### Risks
A plugin that is merely slow on every call is restarted repeatedly; the notice makes that visible and the query timeout is the person's choice.
### Proof
cargo test -p cmd-host --test host.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: Timeouts.hung_after (default 3, zero disables). The worker counts timeouts in a row from the call's own outcome (CallError::Timeout, not the message text); at the limit the answer reads '<timeout>, N times in a row; starting it again', the process counts as gone, and the usual back-off, restart and Restarted notice follow; dropping the old process kills it. Test a_plugin_that_keeps_timing_out_counts_as_hung_and_is_started_again with a 100 ms query timeout and hung_after 2. Awaiting review.

From the review: back-off was forgotten on every timeout below the limit, so a plugin that hangs every time restarted at once each time. Now only an answered call (Health::Fine) forgets it; test a_plugin_that_hangs_again_waits_longer_before_its_second_restart sees restart two carry attempt 2 and arrive after the 2 s step. Awaiting review.
<!-- SECTION:NOTES:END -->
