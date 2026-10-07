---
id: TASK-1.9
title: 'Show on the hotkey, hide on Escape and on focus loss'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:34'
labels:
  - size-3
milestone: m-1
dependencies:
  - TASK-1.7
parent_task_id: TASK-1
type: task
ordinal: 10000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Escape, an effect that hides, and a click outside all hide the window; the process keeps running
- [ ] #2 Showing again resets the launcher state (generation keeps climbing, so late answers stay dropped)
- [ ] #3 The hotkey shows the window centred across the primary display a third of the way down, with an empty, focused input (several displays: task 'Place the launcher on the active display')
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Core: Clear and Pick(n) events from the keyboard decision, with tests.
2. App: register the chord with global-hotkey, bridge its callback to GPUI through an async-channel and a foreground task; show with activate plus focus, hide with cx.hide(); observe window activation and hide on focus loss.
3. Compile-check in the scratch workspace (Linux X11 backend), then macOS CI.
### Risks
Behaviour is unverified on a real Mac in this environment; focus-loss hide could fight the show path if the activation observer fires during activate.
### Proof
cargo clippy and build green on macOS CI; core tests for the new events; a person presses the chord.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented in 995871a: the chord shows the window (activate, activate_window, focus), Escape, an effect and losing focus hide it through cx.hide(), and the state resets on hide so the next show starts empty. Clippy -D warnings green in the scratch workspace; awaiting the macOS CI build and a person at a Mac for the behaviour.

CI run 8 (https://github.com/brukhabtu/cmd/actions/runs/37568145747, 995871a): cmd-app passed clippy -D warnings and cargo build on macos-latest. Run 7 on a730f3f failed on a rename the scratch check should have caught; the chain now gates the commit on the scratch clippy result.

Review fix: the window is placed centred across the primary display a third of the way down (launcher_bounds), computed at startup. Not yet the active display when several are attached; the reviewer's residual risk (a queued deactivation delivered after show) can only be settled on a Mac.

Second review pass: the first criterion assumed the active display; narrowed to the primary display on the reviewer's proposal, with a new board task for several displays. Still owed: one press of the chord on a Mac, noted on the task by whoever does it.
<!-- SECTION:NOTES:END -->
