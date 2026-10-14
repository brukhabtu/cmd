---
id: decision-13
title: >-
  Watchers: items with a Watch action, completion on Tab, and a notify
  capability
date: '2026-10-14 18:31'
status: accepted
---
## Context

The owner wants to watch things that move (a ticket, a pull request) from the launcher and
be told, with Jira only as an example. A watcher needs four things the protocol lacks:

- a way to say "watch this" on a result, and to list and drop watches;
- completion, so `jira proj` can be narrowed to one issue before its actions are chosen;
- a way for a plugin to tell the person something happened while the window is hidden;
- a place to see what moved while away.

What exists: keywords route text to a plugin and strip the word; an item can carry several
actions (`Action`); plugins are long-lived processes with a data directory
(`CMD_PLUGIN_DATA`); decision 12 (proposed) adds plugin-to-host lines behind a capability;
draft 5 is the home query; draft 6 is the Cmd-K actions menu; draft 8 is feeds, providers
as user-supplied commands. Decision 4 says everything but a small set of keys is text, and
that Tab to complete is a protocol change.

## Decision

### Noun, then verb; the host knows no watch

The person types a keyword and some text, picks a row, and chooses an action on it. Watch is
an **action** on an item, and Unwatch the action on a watched one. Plugin-local verbs
(`demo watching`, `demo unwatch X`) are rows the plugin returns for the text after its
keyword. The protocol learns no word `watch`. What a plugin watches, how often it polls, what
counts as a change and where it keeps its list are the plugin's, in its data directory, so
that a restart does not announce old changes again.

The host does not schedule polls. A protocol call has a 3 s timeout and every service
differs; this is the argument decision 12 made for indexing.

### `complete`: one list, one query

An item gets an optional `complete` text. Tab puts it in the input and keeps the window
open; Enter does what Enter does. There is no second autocomplete request: the same query
returns results and the rows that continue typing. A row that stands for no item (a
suggestion such as `demo watching`) has `complete` and no real action, so Enter and Tab do the same.
Rules:

- One row per thing, with `complete` on it; a plugin does not return the item and a
  separate row that completes to it.
- Suggestion rows sort after results unless the plugin scores them higher.
- A row without `complete` does nothing on Tab.
- This is an optional field (decision 9, kind 1): no version, no capability. A host that
  ignores it loses only Tab.
- It amends decision 4: Tab is a key the launcher owns, and acts only on the selected row.

### `notify`: the plugin tells the person

A plugin-to-host line, shaped as decision 12's, behind the capability `notify`:

```json
{"event": "notify", "params": {"id": "PROJ-12", "title": "PROJ-12 moved", "body": "In Review", "open": "https://example.test/PROJ-12"}}
```

- `id`: names the thing within the plugin; a later notice with the same id replaces the
  earlier one in the recent list.
- `title`: required, cleaned like item text. `body` and `open` (a target the host opens on
  click, as `Open`) are optional.
- The host does two things: it posts a macOS notification, and it keeps the last twenty in a
  recent list. The plugin sends it only to a host that named `notify`, and otherwise
  reports nothing; the recent list is then the only place to see what moved.
- A plugin rate-limits itself (one notice per change, and one summary after a wake with many).
  The host also drops a plugin's notices above a small rate, so a bug cannot flood the person.
- It shares decision 12's machinery: the reader that classifies a line as it arrives, and the
  SDK's locked writer. The two capabilities, `tasks` and `notify`, share one task.
- A failing watch (unreachable, unauthorised) is a decision 12 task that stays until
  dismissed, not a notice at every poll.

### What the person sees while away: the home query

Draft 5's blank-input home query: a plugin that wants it declares so in `describe`, and the
host sends `{"text": "", "home": true}` when the window opens with an empty input. The
host's own recent list of notices is the first home content; a plugin's `watching` rows can be
added by that plugin through the same query.

### The demo plugin

`plugins/watchdemo` watches a **local JSON file**, a set of fake tickets (`id`, `title`,
`status`) that the tests and the person edit by hand or with a script. It has no network, no
credential and no vendor code, and it exercises everything: tickets as results with `complete`,
Watch and Unwatch actions, a `watching` verb, a polling thread with state in the data
directory, a diff that sends `notify` for a changed status, a task for an unreadable file,
and home rows for what moved. A provider that runs a command, as draft 8 describes, replaces
the file later and turns it into a real watcher with no vendor code in the repository.

### Deferred

- The `>` mode, a list of every plugin's verbs across the launcher. Verbs the plugins
  declare in an optional `describe` field would feed it. It amends decision 4 and is a
  discoverability feature, not a requirement.
- A menu bar item, and a notification action (Snooze, Mark seen).
- Where secrets live, for a real Jira or GitHub plugin (Keychain through the `security`
  command is the leaning). The demo needs none.
- A cross-plugin "everything I watch" list. Each plugin lists its own for now.

### Assumed, for the owner to confirm

- The names: `complete`, `notify`, `home`.
- Tab acts on the selected row only; suggestions sort after results.
- A notice is cleared on the plugin's restart; the recent list holds twenty and is not kept
  across a quit of the app.
- Posting a macOS notification from an unsigned build may be attributed to another app.
  That is checked on the owner's Mac (TASK-6.1) before the host depends on it.
- The host drops notices above a rate (the leaning: more than 5 in 10 seconds per plugin).

## Consequences

The plan is TASK-6 and its children. In order: the Mac spike on notifications; decision 12's
protocol work (DRAFT-15), which `notify` extends; `complete` and Tab; the notify capability
and the recent list; the home query; the demo plugin; then the user page. `complete` and the
home query do not depend on the reader work and can run alongside it. The docs and the golden
fixture change with each protocol task (CLAUDE.md).
