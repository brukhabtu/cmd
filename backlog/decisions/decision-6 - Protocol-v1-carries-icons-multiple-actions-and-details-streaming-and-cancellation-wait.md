---
id: decision-6
title: >-
  Protocol v1 carries icons, multiple actions and details; streaming and
  cancellation wait
date: '2026-10-07 04:38'
status: proposed
---
## Context

Protocol v0 is one request, one answer: `describe`, `query`, `run`. Milestone 1 made the
host asynchronous without touching the wire, and the first two plugins (calculator,
websearch) fit v0 with room to spare. Task 1.16 asked what the next version should carry.
The candidates, with what each costs the person writing a plugin in Python:

| Candidate | What it gives | What it costs an SDK author |
|---|---|---|
| Icons on items | Recognisable rows: an app bundle, a file type, a symbol | One optional field; nothing in the loop |
| Several actions per item, and Cmd-K to pick one | Open, reveal, copy path, each a verb | Already in v0's `actions`; the window and Cmd-K are the missing half |
| Item details | A preview pane: a definition, a file's metadata, an image | One optional field holding markdown or a path; rendering is the window's problem |
| Streaming results | Rows appear while a slow search is still running | Every `query` becomes a generator, every test has to spell out partial states, and the SDK's loop grows a second message type |
| Cancellation | A superseded query stops burning the plugin's time | The plugin must poll a cancel flag or run its work on a thread; the host already drops stale answers and collapses queued queries, which gives most of the benefit for free |
| Plugin-initiated updates | A clock, a clipboard history that changes on its own | A new direction of message, and a reason for a plugin to hold state; nothing asks for it yet |

## Decision

Version 1 adds three optional fields and changes no method: `icon` on an item (an app
bundle path, a file path, or an SF Symbol name), `details` on an item (markdown, or a
path to render), and nothing new for actions, since v0 already carries a list; v1's work
on actions is in the window (Cmd-K opens the list, Enter runs the first) and in the
document (what each action id is expected to do).

Streaming, cancellation and plugin-initiated updates wait. The host's generation tagging,
stale-answer dropping and query collapsing already keep a slow plugin from hurting the
window, and none of the plugins on the board needs rows before its search finishes. If a
plugin does, it can answer quickly with what it has and let the person type a character
to ask again; that is a v2 conversation with evidence.

The `protocol` number in `describe` becomes 1. A v0 plugin keeps working: every v1 field is
optional and the methods are unchanged, so the host accepts 0 and 1 and the document says
which fields a v0 plugin will not have read.

## Consequences

- Three homes change together, as always: `crates/cmd-core/src/protocol.rs`,
  `python/cmd-sdk/src/cmd_sdk/protocol.py`, `docs/plugin-protocol.md`, plus the adapter
  test. Task 1.24 (icons in results) is the first slice; details and Cmd-K follow.
- Decision 4's reserved Cmd-K row gets its meaning.
- A new effect kind is never optional: the host must decode every effect it is sent, so
  one needs a new protocol version. Version 1 adds no effect.
- The SDK's `Item` grows two optional fields and nothing else; a plugin author's loop is
  untouched, which is the point.
