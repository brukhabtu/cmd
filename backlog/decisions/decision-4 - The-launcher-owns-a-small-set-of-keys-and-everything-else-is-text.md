---
id: decision-4
title: The launcher owns a small set of keys and everything else is text
date: '2026-10-07 03:38'
status: proposed
---
## Context

The window takes raw key events from GPUI and turns them into events for the state
machine. Some keys drive the launcher; everything else is the query. The line between the
two has to be drawn once, so plugins never see a navigation key as text and the person
never loses a character to the launcher.

## Decision

The launcher owns these keys and no others:

| Key | Event | Note |
|---|---|---|
| Escape | hide | Clears the text; the next show starts empty |
| Enter | run the selected item's first action | Enter with nothing selected does nothing |
| Up, Down | move the selection | Clamped to the list |
| Backspace | delete the selection, else the grapheme before the cursor | Option-Backspace deletes the word before the cursor; Cmd-Backspace everything before the cursor, which is the whole text when the cursor is at the end |
| Left, Right | move the cursor | Shift extends the selection; Option moves by word; Cmd moves to the start or the end |
| Cmd-A | select the whole text | |
| Cmd-C | copy the selection | Nothing without a selection; the window stays open |
| Cmd-V | paste the pasteboard's text at the cursor | Line breaks become spaces; a pasteboard without text pastes nothing |
| Cmd-1 to Cmd-9 | run the nth visible row | Counted over the rows on screen; the view tells the state machine how many fit |
| Cmd-K | open the actions of the selected item | Reserved for the actions menu that protocol v1's multiple actions need (task 1.16); dropped until then |
| Cmd-, | open settings | Reserved; nothing until there are settings |

An owned key answers with or without a modifier held, except where the table says a
modifier changes it (Backspace, Left and Right, and the Cmd-letter rows). So Cmd-Enter runs and Cmd-Down moves the selection;
nothing is lost, and the person is never surprised by a key that does nothing.

Everything that produces a character reaches the text through GPUI's input handler, the
same path AppKit uses for `insertText:` and `setMarkedText:`; the key handler no longer
reads `key_char`, it leaves those keys alone and the input method delivers them. A
keystroke with Cmd or Control held and no row above is dropped, not typed. Option is not
a launcher modifier: Option-letter combinations produce characters on macOS and are text.
Shift is text as well.

Text input belongs to the state machine in `cmd-core`, whose `Input` holds the text, the
cursor, the selection and the composition: the view maps a keystroke to an `Event`, and
the input handler maps what the platform sends (typed text, a replacement, a composition,
its end) to an `Event` as well, and nothing more. Dead keys and input-method composition
(IME) work through that path; while a composition is open the input method sees every
key first, so Enter, Backspace, Escape and the arrows edit the composition rather than
the launcher.

Plugins never see keys. They see the text the person typed, with the keyword stripped, and
the id of the item and action the person chose.

## Consequences

- `Event` in `crates/cmd-core/src/state.rs` is the whole vocabulary; a new launcher key is
  a new variant and a row in this table, never a special case in the view.
- Cmd-number counts the visible rows, and each row shows the number that runs it. The
  list scrolls as a window the state machine owns (task 1.12): the view says how many rows
  fit, the state machine keeps the selection inside them, and Cmd-n is the nth of those.
- Option-Backspace and Option-Left and Right are owned although Option is otherwise
  text, because on macOS they produce no character; each key the view takes stops
  propagation, so the input method never sees it as well.
- A plugin that wants a key of its own (Tab to complete, say) is a protocol change, and a
  candidate for protocol v1 (task 1.16), not a view hack.
