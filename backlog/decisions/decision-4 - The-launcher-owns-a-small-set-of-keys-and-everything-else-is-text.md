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
| Backspace | delete backwards | Cmd-Backspace clears the whole text |
| Cmd-1 to Cmd-9 | run the nth visible row | Counted over the rows on screen; the view tells the state machine how many fit |
| Cmd-K | open the actions of the selected item | Reserved for the actions menu that protocol v1's multiple actions need (task 1.16); dropped until then |
| Cmd-, | open settings | Reserved; nothing until there are settings |

An owned key answers with or without a modifier held, except where the table says a
modifier changes it (Cmd-Backspace). So Cmd-Enter runs and Cmd-Down moves the selection;
nothing is lost, and the person is never surprised by a key that does nothing.

Everything that produces a character reaches the text, taken from the keystroke's
`key_char`, which carries the typed character after modifiers and layout are applied.
A keystroke with Cmd or Control held and no row above is dropped, not typed. Option is
not a launcher modifier: Option-letter combinations produce characters on macOS and are
text. Shift is text as well.

Text input belongs to the state machine in `cmd-core`: the view maps a keystroke to an
`Event` and nothing more. Composition from an input method (IME) is the one case that
bypasses the key table: GPUI delivers it through its input handler, and task 1.10 (a real
text input) wires that path. Until then, dead keys and IME composition are not supported.

Plugins never see keys. They see the text the person typed, with the keyword stripped, and
the id of the item and action the person chose.

## Consequences

- `Event` in `crates/cmd-core/src/state.rs` is the whole vocabulary; a new launcher key is
  a new variant and a row in this table, never a special case in the view.
- Cmd-number counts the visible rows, and each row shows the number that runs it. The
  list scrolls as a window the state machine owns (task 1.12): the view says how many rows
  fit, the state machine keeps the selection inside them, and Cmd-n is the nth of those.
- A plugin that wants a key of its own (Tab to complete, say) is a protocol change, and a
  candidate for protocol v1 (task 1.16), not a view hack.
