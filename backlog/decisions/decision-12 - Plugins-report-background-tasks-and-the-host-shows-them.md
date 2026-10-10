---
id: decision-12
title: 'Plugins report background tasks, and the host shows them'
date: '2026-10-10 16:43'
status: proposed
---
## Context

Task 5 (search by meaning) needs an index that is built in the background, and TASK-5.1 asks
whether indexing is something every plugin can plug into. The owner's answer: plugins
report. Draft 4 (deferred, not accepted) had already described the host side: a plugin that
does work between calls (the vault's outbox retrying, a cache refresh) needs a
plugin-to-host event, a host reader that handles lines with no id between calls, and an SDK
that serialises stdout writes from a background thread.

What the code has today:

- A plugin speaks only when spoken to. `PluginProcess::call` in
  `crates/cmd-host/src/process.rs` reads lines only while a call is in flight. It skips a
  line whose id is not the request's, which is how a late answer is dropped.
- A line with no `id` is not a response (`Response.id` is required), so today it fails
  the call it lands in with a decode error. Nothing may send one yet.
- The SDK's `serve` writes from one thread. A build thread writing on its own would
  interleave with an answer.
- Plugins already work in the background on their own threads: the vault drains its outbox,
  the search plugin's providers run in parallel threads, applications refreshes its scan
  (`TtlCache`). The host sees none of it.
- Decision 9 says a message in a new direction is a new version (its third kind).

## Decision

### Plugins report; the host shows

How a plugin indexes is its own: what, which model, how it chunks, where it stores, how it
learns of a change. The host never learns what an index is. It learns that the plugin has
a **task** running, how far along, and whether it failed. Indexing is one task a plugin
can report; the vault's retrying outbox and a slow cache refresh are others (draft 4's
second source). Nothing else is added for indexing: no `status` method, no `reindex`
method.

- To rebuild, a plugin offers a row whose action starts the rebuild. `run` already does
  work and returns an effect, so this needs no new method.
- A build never blocks a query or the window. The plugin builds on its own thread, keeps
  its progress durable in `CMD_PLUGIN_DATA` so a quit resumes, and `query` answers from
  what is built so far, saying so in a row when that matters. This is the plugin's duty;
  the host cannot enforce it, and a plugin that breaks it costs itself the query timeout.

### The message

A line from the plugin with an `event` key and no `id`:

```json
{"event": "task", "params": {"id": "index", "label": "Indexing notes", "state": "running", "done": 120, "total": 900, "detail": "meetings/2026"}}
```

- `id`: names the task within the plugin, so a later line replaces an earlier one.
- `label`: short text for the person; required.
- `state`: `running`, `done` or `failed`; required.
- `done` and `total`: optional non-negative integers, `done` at most `total`. With neither,
  the task has no progress to show.
- `detail`: optional text, one line.

The host keeps the latest line per task id per plugin. `running` is shown until replaced.
`done` is shown briefly and dropped. `failed` stays until the person dismisses it (draft
4's decision: a capture lost in the background is the worst outcome). A restart of the
plugin clears its tasks, so a plugin reports again after `describe`. Text is cleaned as
item text is: control characters out, cut at 160 characters.

### A capability, not a version

Decision 9 lists "a message in a new direction" as a new version. That rule exists because
a host that cannot read a line breaks. Here the plugin sends the line only to a host that
named the capability in `describe`, `"tasks"`, and a plugin that does not hear it does
what it did before: reports nothing. That is exactly the shape of decision 9's second
kind (the plugin has a fallback to choose). So the protocol stays at 1 and this decision
**amends decision 9**: a message in a new direction is a capability when the plugin has
the choice not to send it, and a new version when the sender has no such choice.

### What changes in the host

- The reader thread that already exists in `PluginProcess::spawn_in` classifies each line
  as it arrives, not when a call asks: a line with `event` goes to a task channel, any
  other goes to the response channel as today. A line that is neither is `NotProtocol` as
  before. A malformed task line is dropped and noted as trouble for that plugin; it never
  fails a call.
- Reports arrive as a `HostEvent::Task { plugin, task }` for the window, like an answer.
  The host holds only the latest state per task, so a flood costs the reading of lines and
  nothing more; the window redraws at most every 250 ms for them.
- The host sends `"tasks"` in `capabilities`.

### What changes in the SDK

- `Plugin` and `serve` own the protocol stream. A new `report(task)` function may be called
  from any thread; it writes its line under the same lock `serve` takes for answers, so
  lines never interleave. Before `describe` has agreed the capability, or when the host did
  not name it, `report` does nothing.
- A throttle in `report`: a `running` update with the same state arrives at most twice a
  second; a change of state, a `done` and a `failed` are always sent.
- The task shape is checked like an item (a title that is not text, a `done` above `total`
  raise to the caller, not into the protocol).

### The first slice in the window

A line in the status line for the running tasks: "search: indexing notes 120/900".
A failed task is a row-less line that stays until dismissed. This shares the status line
with start trouble (task 1.39) rather than adding the spinner of draft 4, which stays
deferred. The spinner and the hover are a later look at the same data.

### Who adopts it

- The embeddings provider kind of the search plugin (task 5), the first user: it reports
  its build.
- The search plugin could also report a qmd index it triggers, if it ever does.
- The vault's outbox is not an index but fits the same message (`3 waiting`, then `failed`
  on a capture it cannot write), and is the reason the message says task, not index.
- Applications and files do not need it.

Only the first is planned. A contract that fits one user is a smell, and the vault is the
second user who would show whether the shape is right; the shape is kept small (id, label,
state, done, total, detail) so that a second user does not change it.

### Deferred

- A macOS notification for a failure while the window is hidden, and a menu bar item
  (draft 4: a new effect, so a protocol bump).
- The host scheduling work (battery, idle, quiet hours). Plugins decide when to build.
- The spinner and the hover.
- The host asking a plugin to start or pause a task.

### Assumed, for the owner to confirm

- The message and capability are named `task` and `tasks`, not `index`.
- A failed task stays until dismissed, and the first dismissal gesture is a key in the
  window that the later task decides.
- `done` is shown briefly (a few seconds) and dropped; a plugin that wants a result to
  stay reports it as an item.
- Two reports a second per task is the SDK's throttle; the host redraw every 250 ms.
- Rebuilding is a row the plugin offers, not a host button.

## Consequences

- Three tasks follow, in this order: the host reader and the SDK writer with a golden
  fixture for the new line (protocol; docs/plugin-protocol.md changes with them); the
  window's status line; the search plugin's embeddings kind reporting its build (task 5).
- Decision 9 gets a short amendment to its third kind.
- `docs/plugin-protocol.md` documents the line, the capability and the host's handling of
  a line between calls. The Rust side, the Python side and the adapter test change
  together (CLAUDE.md).
- Draft 4 shrinks: its plugin-to-host event is this decision; what stays there is the
  spinner, the hover, the host's own start-up work as tasks, and the hidden-window
  notification.
