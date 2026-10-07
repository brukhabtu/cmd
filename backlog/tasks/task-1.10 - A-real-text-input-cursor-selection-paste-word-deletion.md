---
id: TASK-1.10
title: 'A real text input: cursor, selection, paste, word deletion'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 11:00'
labels:
  - size-5
milestone: m-1
dependencies:
  - TASK-1.8
parent_task_id: TASK-1
type: task
ordinal: 11000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Left and right move the cursor; Shift extends a selection; Cmd-A, Cmd-C, Cmd-V and Cmd-Backspace do what macOS does
- [ ] #2 IME composition (for example Japanese input) works, verified by hand on macOS
- [ ] #3 The state machine in cmd-core stays the only owner of the text; the view renders it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Input in cmd-core: a pure text model with cursor, selection and composition range, byte offsets, grapheme and word motions, a UTF-16 bridge, under unit tests.
2. The state machine gains Delete(Motion), Move, SelectAll, Copy, Paste, Replace, Compose and Unmark; Backspace and Clear go; Step::Copy; edits requery only when the text changed.
3. cmd-app: an InputElement draws the line, cursor, selection and underline and installs an EntityInputHandler on LauncherView, so typing, dead keys and IME reach the state machine through gpui's input handler; on_key stops reading key_char and consumes every owned key.
4. Decision 4's key table and docs/architecture.md follow; the Mac hand check of AC #2 is recorded as owed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed (worktree-wf_1af770a2-fcd-1, merged forward onto ccr-16512bde-x72oqp 6b3f8e6 without conflict):
- crates/cmd-core/src/input.rs: Input, the one owner of the text, cursor, selection (anchor) and input-method composition (marked range), in byte offsets; Motion (grapheme, word, line) via unicode-segmentation; insert, replace, paste (line breaks to spaces), compose (selection relative to the composed text, offset by the range start), unmark, delete, move_to (Shift extends, a step collapses a selection as macOS does), select_all; the UTF-16 bridge and utf16_to_byte. 15 unit tests.
- crates/cmd-core/src/state.rs: Launcher.text became input: Input with text(); Event gains Delete(Motion), Move, SelectAll, Copy, Paste, Replace, Compose, Unmark (Backspace and Clear go); Step::Copy keeps the window open; an edit requeries only when the text changed, moves and selection never do; edits live in Launcher::edit to keep apply under clippy's length limit. 9 new state tests.
- crates/cmd-app/src/input.rs: InputElement shapes the line, draws the selection, the cursor (when focused) and the composition underline, installs the input handler with window.handle_input; impl EntityInputHandler for LauncherView turns every platform write into an Event through handle, so the view keeps only last_line and last_bounds (AC #3: grep key_char crates/cmd-app returns nothing).
- crates/cmd-app/src/main.rs: on_key reads a pure key() (decision 4's table: Backspace with Option and Cmd, Left and Right with Shift, Option and Cmd, Cmd-A, Cmd-C, Cmd-V, the launcher keys, other Cmd and Control chords dropped, the rest left to the input method), stops propagation on every key it takes, never reads key_char; perform handles Step::Copy; input_row holds the element; 5 unit tests of key(). The run closure in main() is untouched.
- Decision 4's key table and text paragraphs, docs/architecture.md (Not yet), the c4 ui-to-macos edge.
Evidence: cargo test -p cmd-core 64 passed; scratch workspace cargo clippy -p cmd-app --all-targets -D warnings clean and cargo test -p cmd-app 12 passed; scripts/check.sh: all checks passed.
Owed on a Mac (AC #2 and the look of AC #1): Japanese Romaji input, a i gives underlined あい, Enter commits and the list refreshes; gpui's a i left down up enter enter gives 愛; Option-E then E gives é; Ctrl-Cmd-Space emoji palette inserts; Escape mid-composition cancels the composition, not the window; no doubled characters; key repeat; cursor, selection and underline drawn in both appearances; Shift, Option and Cmd with the arrows; Cmd-V from the real pasteboard; Cmd-Backspace with a selection against a Cocoa field. Tab no longer types a tab character.
Follow-ups filed as TASK-1.39 (Cmd-X, forward Delete, Home and End, mouse, blinking cursor); renumber if another branch took 1.39 first.
<!-- SECTION:NOTES:END -->
