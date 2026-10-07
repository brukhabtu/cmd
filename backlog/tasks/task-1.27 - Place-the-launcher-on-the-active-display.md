---
id: TASK-1.27
title: Place the launcher on the active display
status: In Progress
assignee: []
created_date: '2026-10-07 04:34'
updated_date: '2026-10-07 11:27'
labels:
  - size-2
milestone: m-1
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today launcher_bounds in crates/cmd-app/src/main.rs positions the window on the primary display once at startup. GPUI offers cx.displays() and the active window's display; the show path should pick the display and recompute the bounds each time.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With several displays attached, the window shows on the display that holds the mouse pointer (or the active window), recomputed on every show
- [ ] #2 The bounds follow a changed display arrangement without restarting the app
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Pure placement in cmd-core (display under the pointer, centred a third down, clamped) with unit tests; the shell reads displays and pointer via CoreGraphics on macOS; reveal() recomputes on every show and reopens the window on another display since gpui 0.2.2 cannot move a window.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What landed (Linux-proven, Mac owed):
- crates/cmd-core/src/placement.rs: the pure decision. display_under picks the display holding the pointer (half-open rects, so a shared edge belongs to one display), else the primary, else the first; launcher_origin centres across and a third down, clamped at 0; place composes them; Placement::matches tells already-there from move (within a point). 12 unit tests.
- crates/cmd-app/src/displays.rs: what the shell sees. On macOS the displays' rects come from CGDisplay::bounds and the pointer from a null CGEvent's location (one global space, no permission); elsewhere GPUI's own display bounds and no pointer, so the Linux scratch clippy compiles the whole show path. The f64-to-f32 narrowing is in two cfg-neutral helpers so the pedantic cast lints are met on Linux.
- crates/cmd-app/src/main.rs: launcher_bounds and toggle are gone. LauncherView::new no longer takes a window; attach() joins the view to each window (activation and appearance observers, focus). open_launcher() opens the PopUp with WindowOptions.display_id and display-relative bounds, at start-up and on every reopen. reveal() is the chord: hide if shown, else place afresh, and when the window is not on that display at that origin, remove it and open a new one (GPUI 0.2.2 cannot move an open window), then show. A Shell global holds the view and the current window handle. The host relay and bring_up_host now update the view entity, not a window handle, so a reopened window never cuts the host off.
- crates/cmd-app/Cargo.toml: core-graphics 0.24 for macOS (already in the lock as GPUI's dependency; Cargo.lock gains only the edge).
- docs/architecture.md and the core.c4 description: cmd-core also decides where the window sits.

Deviations from the plan: the plan's placement() returning (Option<DisplayId>, Bounds) became launcher_placement() returning Option<(DisplayId, Placement)>, so reveal can ask Placement::matches; open_launcher returns Option and logs a window that would not open on a reopen rather than panicking (start-up still expects it). Task 1.41 edits start_host_beside in the same file at the same time; this change leaves start_host_beside and the cmd-startup thread untouched but does change bring_up_host's second parameter from WindowHandle to Entity, and main()'s run closure, so a merge there needs care.

The criterion's 'or the active window' is not done: GPUI's active_window sees only our own windows, and another app's frontmost window needs Accessibility, which decision 5 refuses. The pointer decides, the primary display is the fallback.

For the milestone skill review (not edited here, the eval gate): the Displays bullet of .claude/plugins/cmd-dev/skills/gpui-for-cmd/SKILL.md is wrong against gpui 0.2.2's source. On macOS PlatformDisplay::bounds() returns origin (0,0) for every display (only the size is real); Window::bounds() is relative to the window's own screen; WindowOptions.display_id plus Windowed bounds opens the window on that display with the origin relative to the display's top-left; nothing moves a window once open (PlatformWindow has only resize), so remove_window then open_window is the public route; u32::from(DisplayId) is the CGDirectDisplayID; window.mouse_position() is window-relative.

Evidence (Linux):
- cargo test -p cmd-core placement: test result: ok. 12 passed
- cargo test --workspace --exclude cmd-app: cmd-core test result: ok. 77 passed, every suite ok
- cargo clippy --workspace --exclude cmd-app --all-targets -- -D warnings: clean
- scratch workspace cargo clippy -p cmd-app --all-targets -- -D warnings: Finished, exit 0; cargo test -p cmd-app there: 12 passed
- scripts/check.sh: all checks passed (LikeC4 model valid, 15 files)
- macOS CI's app job is the first compile of the core-graphics arm under the pedantic set: read that run before closing.

Owed on a Mac with two displays (criteria stay unticked until a person writes the result here):
1. Pointer on the secondary display, press the chord: the window appears there, centred, a third down. Escape, move the pointer to the primary, press: it appears on the primary.
2. Press twice with the pointer on the same display: no reopen, no flash.
3. While the app runs, swap the displays' arrangement in System Settings and change one display's resolution; press again: the window is on the pointer's display at the new bounds.
4. A single display behaves as 1.9 left it (settle 1.9's owed press in the same session).
5. No Accessibility or Input Monitoring prompt appears when the pointer is read.
6. The focus-loss observer does not hide the freshly reopened window during the swap, and typing works at once in the reopened window.
7. Whether CGDisplayBounds/CGEvent location agree with GPUI's display-relative placement to the point, and whether window.bounds() of the titleless PopUp equals the content rect (if not, every show reopens: slow, not wrong).
<!-- SECTION:NOTES:END -->
