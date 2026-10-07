---
id: TASK-1.12
title: >-
  Window look: borderless, rounded, vibrancy, selection that follows the
  keyboard
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 07:22'
labels:
  - size-3
milestone: m-1
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 13000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No title bar, rounded corners, a translucent material behind the list
- [x] #2 Rows show title and subtitle; the selected row is visible and scrolls into view when the list is long
- [x] #3 Looks right in light and dark appearance
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) cmd-core state.rs: Launcher gains first_visible and rows (a window onto the list), new(rows), keep_selected_on_screen after Up, Down and the Answered merge, Pick counts from first_visible when rows > 0, visible() returns the on-screen slice; seven unit tests. 2) cmd-app main.rs: layout constants with a compile-time fit assertion, Palette from Window::appearance with observe_window_appearance, three row helpers, translucent tinted root over WindowBackgroundAppearance::Blurred, rows from state.visible(). 3) decision-4: Cmd-number counts visible rows. Then cargo fmt, clippy, tests, scratch-workspace cmd-app clippy and build, scripts/check.sh.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed on worktree-wf_4dd46466-293-1 (not pushed):
- crates/cmd-core/src/state.rs: Launcher owns a window onto the list: first_visible and rows (0 = the view has not said, every row on screen), Launcher::new(rows), visible(), keep_selected_on_screen() after Up, Down and each merged answer, Pick(n) counted from first_visible and Nothing past the last visible row; apply() split so pick() and merge_answer() keep it under clippy's 100 lines. Seven new unit tests on Launcher::new(3) with five hits; four of them fail with the window logic stubbed out, the other three pin requery, reset and visible().
- crates/cmd-app/src/main.rs: INPUT_HEIGHT, STATUS_HEIGHT, ROW_HEIGHT, VISIBLE_ROWS = 7 with a compile-time assert that they fit HEIGHT; Palette from Window::appearance (dark for Dark and VibrantDark) with translucent tints; observe_window_appearance redraws on a light/dark switch; input_row, status_line (fixed height, message in warning else waiting in muted) and result_row (title, subtitle, Cmd-number at the right) helpers; rows come from state.visible(); root is rounded_2xl over WindowBackgroundAppearance::Blurred.
- decision-4: Cmd-1 to Cmd-9 count the visible rows; the consequence reworded as done.

Evidence: cargo fmt --all --check clean; cargo clippy --workspace --exclude cmd-app --all-targets -- -D warnings clean; cargo test --workspace --exclude cmd-app: cmd-core 39 passed (32 before), cmd-host 14 + 7 + 3 + 2, cmd-host bin 3, protocol 10; scratch workspace (xattr patch) cargo clippy -p cmd-app --all-targets -- -D warnings exit 0 and cargo build -p cmd-app --release links target/release/cmd (26 MB); scripts/check.sh: all checks passed.

gpui 0.2.2 facts verified from the registry source, for the next gpui-for-cmd skill review (SKILL.md untouched because of the eval gate): WindowOptions.window_background: WindowBackgroundAppearance (platform.rs:1121; variants Opaque, Transparent, Blurred at platform.rs:1310); on macOS Blurred makes the NSWindow non-opaque and inserts an NSVisualEffectView below the content (platform/mac/window.rs:256, 1277-1300); Window::appearance() -> WindowAppearance (window.rs:1711; variants Light, VibrantLight, Dark, VibrantDark; Copy; not non_exhaustive; platform.rs:1279); Context::observe_window_appearance(&self, &mut Window, FnMut(&mut T, &mut Window, &mut Context<T>)) -> Subscription (app/context.rs:465); rgba(0xRRGGBBAA) (color.rs:20); Rgba is Copy and converts into Fill and Hsla; rounded_lg, rounded_xl and rounded_2xl are 8, 12 and 16px (gpui-macros styles.rs:1296-1308); truncate() is overflow_hidden + whitespace_nowrap + text_ellipsis (styled.rs:123). Clippy: similar_names flagged a binding named hint beside a parameter named hit; cast_precision_loss needs an allow on the usize-to-f32 cast in the const assert.

Owed to a person on a Mac (CI builds the app; none of this is seen on Linux): 1) press the chord and see no title bar, 16px rounded corners with the shadow following them, and the blur showing through the tint; 2) switch System Settings between light and dark with the window up and see the palette flip; 3) with a plugin that answers more than seven rows (a ten-line SDK plugin returning twenty items in a CMD_PLUGINS directory), press Down past the seventh row and see the list shift with the highlight on screen, and Cmd-3 run the third row on screen rather than the third in the list; 4) judge whether gpui's Selection material reads flat beside Spotlight; the fallback is WindowBackgroundAppearance::Transparent with a more opaque tint, one line in main().

Not done, on purpose: no scroll container, so the mouse wheel does nothing (the criterion is keyboard-driven); the window stays a fixed 420px, so a short list leaves an empty translucent area (Window::resize is a follow-up); no plugins/index.toml entry, nothing new belongs there.

Closed on the reviewer's verdict (CLOSE) against worktree commit 915ec3a, merged as 27b4644. Owed on a Mac, in one sitting: press the chord and see no title bar, 16 px rounded corners with the shadow following them and the blur through the tint; switch System Settings between light and dark and see the palette flip; with a plugin answering twenty items press Down past the seventh row and see the list shift, Up at the top scroll back, and Cmd-3 run the third row on screen; judge the Selection material against Spotlight (fallback: WindowBackgroundAppearance::Transparent with a more opaque tint). Left out on purpose: no scroll container (mouse wheel does nothing) and the fixed 420 px window (a short list leaves an empty translucent area; TASK-1.37).
<!-- SECTION:NOTES:END -->
