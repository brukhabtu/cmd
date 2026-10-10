---
id: decision-9
title: 'What the kernel, the SDK and a plugin each own, and how the contract grows'
date: '2026-10-08 18:32'
status: proposed
---
## Context

The architecture review of 2026-10-08 (task 2) found the launcher about to take plugins
that keep state, such as a vault plugin that writes to Obsidian, and plugins fed by
commands the person writes, such as a calendar provider. The contract they would stand
on has gaps. Decision 6 promises a `details` field that the code does not have. A plugin
answers `describe` with protocol 1 whatever the host speaks. Nothing says which new field
needs a new version.

What the code has today. The host sends its version (1) in `describe` and loads a plugin
that answers 0 or 1 (`ACCEPTED` in `crates/cmd-core/src/protocol.rs`). Neither side
rejects a field it does not know, so an extra field is ignored. An item has `icon` and
no `details`. An unknown effect kind fails the whole answer. (An unknown icon kind did too,
until task 2.3 made the host drop only that icon.)

## Decision

### Who owns what

The kernel is the launcher app: `cmd-core` decides, and `cmd-host` and `cmd-app` perform.
The kernel owns a thing when the thing must see every plugin, needs the operating system,
or must look the same everywhere. The SDK owns what every plugin would otherwise write for
itself and the kernel need not see. The plugin owns the rest.

| Owner | Owns |
|---|---|
| core | the protocol's types, its versions and capability names; routing, keywords and keyword clashes; merging and ranking; the state machine |
| host | plugin processes, deadlines, restarts, the file watch, each plugin's data and config directory |
| window | the hotkey, keys, the pasteboard, opening targets, drawing, performing effects |
| SDK | the serve loop, encoding at the agreed version, keeping stdout for the protocol, reading the data and config directory, a subprocess call with a deadline, a TTL cache, typed provider records |
| plugin | what it finds and does, its config schema, its outbox, the tools it calls (the obsidian CLI, provider commands) and their credentials |

The host picks a data and a config directory for each plugin, outside the plugin's code
directory, which it watches for changes to restart on. The data directory is not
watched, so a plugin writing there is not restarted; the config directory is, and a
change to a plugin's config restarts it. The host passes them as `CMD_PLUGIN_DATA` and
`CMD_PLUGIN_CONFIG` (task 2.5). They are environment, not protocol: no field, no
version, no capability. The SDK reads them and never makes a path up; with one missing
it raises an error that names the variable.

### How the contract grows

Every change to the contract is one of three kinds.

1. **An optional field.** A host that ignores it still does right by the person, so the
   plugin sends it whatever the host is, unless the version the two agreed on predates the
   field, when the SDK leaves it out (task 2.3 does so for `icon` at version 0). No new
   version, no capability. Examples: the
   flag that asks for blank input (draft 5), `details` when it is built.
2. **A capability.** The plugin must behave differently when the host does not read the
   field. The host names it in `describe`, and the plugin uses it only then. The first is
   `keywords`: a plugin with several keywords sends them when the host names `keywords`,
   and otherwise declares no keyword and matches the first word itself. A capability is
   named only where a plugin has a fallback to choose.
3. **A new version.** Anything the host must decode to keep working, or that changes what
   an existing message means: a new effect kind (paste, set-input), a new icon kind, a new
   method, a message in a new direction, a field that becomes required or changes meaning.
   (Decision 12 proposes an exception: a plugin-to-host message that the plugin sends only to
   a host that named it in `capabilities`, and leaves unsent otherwise, is a capability.)
   Kinds stay versioned after task 2.3 makes the host decode item by item: that limits the
   damage of a mistake and is no licence to send a kind the host does not know.

### Negotiation

The params of `describe` carry `protocol`, the host's version, and `capabilities`, a list
of names; a missing list is an empty one. The plugin answers with the lower of the host's
version and its own, and from then on sends only what that version and those capabilities
allow. The SDK holds to this for the plugin, lets the plugin read both, and answers a
plugin that returns a kind the agreed version lacks with an error naming it, so the host
never gets a line it cannot read. The host loads every version from 0 to its own, and
sends a plugin only what the version it answered has. Dropping an old version takes a
decision.

### Outside tools

A plugin that calls an outside tool owns the call. The host's deadlines (3 s for `query`,
10 s for `run`) bound it from outside and are not a plan.

- **Obsidian.** The vault plugin reaches Obsidian only through the obsidian CLI, at an
  absolute path from its config. In `query` a call has its own deadline, shorter than the
  host's, and is never made in a way that can launch Obsidian. A write goes to an outbox
  in the data directory first and leaves it when the CLI has written it; the plugin
  retries it, so a capture made while Obsidian is closed or slow is kept. The outbox's
  states, retries and duplicate rule are task 2.7's.
- **Providers.** This is the rule for feed providers, whose answer does not depend on what
  is typed (a search provider answers the typed text, so it runs in `query` under its own
  deadline: decision 11). A feed provider is a command the person writes, at an absolute path. It runs
  once per refresh: one request on stdin, one answer on stdout, then it exits. It never
  runs in `query`. A refresh on the plugin's own thread fills a cache, and `query` reads
  the cache only. Its credentials are its own, never in this repository. The contract's
  shape is draft 8's.

Task 2.4, the CLI spike, does not change these rules. What it finds changes the vault
plugin:

| The spike asks | If yes | If no |
|---|---|---|
| Do warm `search` and `tasks` answer well inside 2 s? | `query` calls the CLI with a 2 s deadline | `query` reads a cache refreshed off the query path, as a provider's is |
| Does a call launch Obsidian when it is closed? | the plugin checks Obsidian is running before any call in `query` | the check saves time and guards nothing |
| Does a call hang while Obsidian is paused? | every call is killed at its deadline, and a timed-out write may have landed, so the outbox needs a duplicate rule | the same rules, met less often |
| Can the CLI write while Obsidian is closed? | the outbox drains at once | writes wait for Obsidian, and task 2.7 decides whether direct file writes are worth the risk of writing under Obsidian |

Its four open behaviours (content with a template, where a template file lands, the
fields of `tasks format=json`, whether `daily:append` creates the daily note) shape task
2.7's config, not this decision.

### Deferred

- **Messages a plugin starts.** One answer to each request, one request at a time, is what
  lets a plugin be a plain loop and lets the host treat any other line on stdout as an
  error. A message from the plugin needs a host reader for lines between calls, an SDK
  that serialises writes from several threads, and a new version. Nothing in task 2
  needs it: the outbox and the provider cache work inside the plugin.
- **Background-task indicators** (draft 4). Work a plugin does between calls can only
  reach the window as a message the plugin starts. Calls in flight need no protocol, but
  the owner deferred the draft whole. Until then a plugin shows pending or failed work as
  rows in its next answer. When they come, a failure stays until dismissed.

### Assumed, for the owner to confirm

- The kernel includes the window crate, though the task named only the host and the core.
- The data and config directories travel as environment, so they need neither a version
  nor a capability; with one missing, the SDK raises rather than guess.
- `capabilities` is the name of the list, and missing means empty.
- The blank-input flag needs no capability; several keywords do.
- A kind the agreed version lacks is an error from the SDK, never a quiet fallback such as
  paste turned into copy.
- Amending decision 6 is enough; superseding it would leave two records for one version.

## Consequences

- Task 2.3 builds the negotiation as written. The host stays at version 1: `capabilities`
  is a new param an older SDK ignores, and an older SDK answering 1 still loads.
- Draft 5's several keywords is the first capability; its blank-input flag is an optional
  field. Paste and set-input wait for version 2, which nothing in task 2 needs.
- Tasks 2.5 and 2.6 build the two variables and the helpers that read them. The host
  learns nothing of Obsidian or providers.
- `docs/plugin-protocol.md` owes the three kinds of change in place of its Versions
  paragraph, the negotiation, and the two variables. Tasks 2.3 and 2.5 write them, since
  they change that document with the code.
- Decision 6 is amended to match the code: version 1 carries `icon`, and `details` waits.
