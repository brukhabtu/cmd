# Plugin protocol, version 1

How the launcher talks to a plugin. The Rust side is `crates/cmd-core/src/protocol.rs`, the
Python side is `python/cmd-sdk/src/cmd_sdk/protocol.py`, and
`crates/cmd-host/tests/calculator.rs` proves the two agree by driving the real calculator
and websearch plugins. A change to the protocol changes all three in one commit, and the
golden exchanges below with them.

## A plugin is a directory

```
calculator/
  cmd-plugin.toml
  pyproject.toml
  src/calculator/...
```

`cmd-plugin.toml` says what to run:

```toml
name = "calculator"
command = ["uv", "run", "--quiet", "calculator"]
```

The host runs `command` with the plugin directory as the working directory, stdin and stdout
piped, and stderr inherited. A plugin logs to stderr. Stdout belongs to the protocol: any
line on it that is not a protocol message (an answer or an event) is reported as an error
that quotes the line.
The Python SDK keeps the real stdout for the protocol and points `sys.stdout` at stderr
while it serves, so a stray `print` is logged instead; a program the plugin starts still
inherits the real stdout unless the plugin gives it somewhere else.

Where the host looks for plugin directories is the host's business: the per-user directory
(`~/Library/Application Support/cmd/plugins` on macOS), `./plugins` under the working
directory when it exists, or the directories in `CMD_PLUGINS` when that is set. Two
directories declaring one name are not both run: the first in that order is, and the
second is reported as a start failure naming both.

## Where a plugin keeps its data and config

The host gives each plugin two directories and says where they are in the environment of
the plugin process, on every start and restart. They are environment, not protocol: no
field, no version, no capability. `<name>` is the `name` in the manifest, and the cmd
directory is the parent of the per-user plugin directory
(`~/Library/Application Support/cmd` on macOS).

| Variable | Directory | The host |
|---|---|---|
| `CMD_PLUGIN_DATA` | `<cmd directory>/plugin-data/<name>/` | creates it before the plugin starts and does not watch it |
| `CMD_PLUGIN_CONFIG` | `<cmd directory>/plugin-config/<name>/` | does not create it, and watches it |

Both are absolute paths. A plugin writes what it keeps (state, caches, an outbox) in the
data directory: a write there never restarts it, which a write in its own directory does,
because that directory is watched. The user's settings for the plugin are the file
`config.toml` in the config directory. A change to anything in that directory, or the
directory appearing after the launcher started, starts the plugin again like a change to
its code, and the window says "reloaded". A plugin must expect the config directory not
to exist. A manifest name that cannot be one directory name (empty, `.`, `..`, or
holding a path separator) is a start failure.

## Transport

UTF-8 JSON, one message per line, `\n` terminated.

The host sends requests:

```json
{"id": 1, "method": "query", "params": {"text": "2+2"}}
```

The plugin answers each request with one line carrying the same `id`, either a result:

```json
{"id": 1, "result": {"items": [{"id": "4", "title": "4"}]}}
```

or an error:

```json
{"id": 1, "error": {"code": "plugin_error", "message": "ZeroDivisionError: division by zero"}}
```

Ids increase for the life of the process. The host sends one request at a time and waits
for its answer, so a plugin can be a plain loop. An answer that arrives after the host gave
up is dropped. A plugin may also start a line of its own, an event with no `id`; there are
two, a task report (see Tasks) and a notice (see Notifications), and the host reads either
whenever it arrives.

## Methods

| Method | Params | Result | When |
|---|---|---|---|
| `describe` | `{"protocol": 1, "capabilities": ["tasks", "notify"]}` | Description | Once, right after the process starts |
| `query` | `{"text": "..."}`, or `{"text": "", "home": true}` | `{"items": [Item]}` | On every change to the typed text that reaches this plugin; the `home` form only to a plugin that declared `home` (see Routing) |
| `run` | `{"item": "...", "action": "..."}` | `{"effect": Effect}` | When the person presses Enter on one of this plugin's items |

### Description

```json
{"name": "calculator", "version": "0.1.0", "protocol": 1, "keyword": "calc"}
```

`protocol` is the version the plugin and the host now speak, as agreed below. `keyword` is
optional; see Routing. `home` is optional too, `true` or absent: the plugin wants the
window's blank input (see Routing). It is an answer field with no version and no
capability (see How the contract grows): a host that does not know it never asks, and a
plugin that leaves it out is never asked.

### Negotiation

The params of `describe` carry `protocol`, the version the host speaks, and
`capabilities`, a list of names for behaviour the host supports beyond its version. A
missing list is an empty one, as from a host older than the list. This host speaks 1 and
names two capabilities, `tasks` (see Tasks) and `notify` (see Notifications), so it sends
`{"protocol": 1, "capabilities": ["tasks", "notify"]}`.

The plugin answers with the lower of the host's version and its own, and from then on
sends only what that version and those capabilities allow. The host loads a plugin that
answers any version from 0 to its own, and refuses any other with a message naming the
plugin and the range. It does not track the version a plugin answered: every method
exists at version 0, so it sends them all. Dropping
an old version takes a decision (decision 9).

A version 0 host, which sent `{"protocol": 0}`, loaded only a plugin that answered 0, so a
plugin that always answered 1 did not run there. The SDK answers such a host with 0, so a
plugin written today loads there too.

The Python SDK does this for a plugin. It answers `describe` with the lower version, and
then:

- leaves out a field the agreed version does not have. At version 0 that is `icon`: a
  version 0 host would ignore it, and leaving it out costs nothing it would show.
- answers a plugin that returns a kind the agreed version lacks, an effect kind or an
  icon kind, with a `plugin_error` naming the kind and both versions, so the host is never
  sent a line it cannot read. No kind is newer than version 1 yet, so this guards version 2.
- gives the plugin the agreed version and the host's capabilities: `Plugin(describe=...)`
  is called with them before the description is sent, and its answer is sent instead.
- writes a task report only when the host named `tasks` (see Tasks), and a notice only when
  it named `notify` (see Notifications).

### How the contract grows

Every change to the contract is one of three kinds (decision 9).

1. **An optional field.** A host that ignores it still does right by the person, so a
   plugin sends it whatever the host is. No new version, no capability. Neither side
   rejects a field it does not know.
2. **A capability.** The plugin must behave differently when the host does not read the
   field. The host names it in `capabilities`, and the plugin uses it only then, falling
   back otherwise. A capability is named only where a plugin has a fallback to choose. The
   first are `tasks` (see Tasks) and `notify` (see Notifications); `keywords`, for a plugin
   with several keywords, will be another.
3. **A new version.** Anything the host must decode to keep working, or that changes what
   an existing message means: a new effect kind, a new icon kind, a new method, a message
   in a new direction, a field that becomes required or changes meaning. One exception
   (decision 12): a message the plugin starts, sent only to a host that named it in
   `capabilities` and left unsent otherwise, is a capability, because the plugin has the
   choice not to send it. A message in a new direction is a capability when the plugin has
   that choice, and a new version when the sender has none.

Version 1 added `icon` to an item (decision 6), which decision 9 would now call an optional
field; its kinds are versioned like any other kind. The host decodes an answer item by
item (see Item), which limits the damage of a kind sent by mistake and is no licence to
send one.

### Item

```json
{
  "id": "4",
  "title": "4",
  "subtitle": "Press Enter to copy",
  "score": 0.8,
  "actions": [{"id": "copy", "title": "Copy"}],
  "icon": {"kind": "symbol", "name": "equal"},
  "complete": "calc 4"
}
```

`id` is what comes back in `run`. `subtitle`, `score`, `actions`, `icon` and `complete` are
optional.

The host decodes the items of an answer one by one. An item it cannot read, one without a
`title` say, is left out on its own: the rest are shown, and the window says how many
items the plugin's answer lost and why, as it says any other trouble with a plugin.

`score` is a confidence between 0 and 1 for a fuzzy match, and a finite number: JSON has no
NaN or infinity, and the SDK answers an item that has one with a `plugin_error`. Leave it
out for a definite answer: the host ranks an item without a score above every item with
one, so a calculator's `4` sits above an application whose name happens to contain a 4.
The host clamps a score outside 0 to 1 into it, so a score of 7 ranks as 1 and cannot
outrank another plugin's 1.

`actions` are what Enter can do. The first is the default. With no actions the host sends
`run` with action `"default"`.

`complete` is the text Tab puts in the input (decision 13). Tab replaces the whole input
with it, puts the cursor at the end and keeps the window open; the input has then changed,
so the host asks the plugins about the new text exactly as if the person had typed it.
There is no second request for completions: one query returns the results and the rows
that continue the typing. Tab acts only on the selected row, and a row without `complete`
does nothing on Tab. Give the row that is the thing its own `complete`; do not return the
thing and a second row that completes to it.

A row with `complete` and no `actions` is a suggestion: it stands for no item, so there is
nothing for Enter to run, and Enter (or Cmd and a number) does what Tab does. A row with
actions keeps Enter for its first action even when it has `complete`. Suggestions rank
after results: a suggestion without a `score` sorts below every other row, scored or not,
and a plugin raises one by giving it a `score`, when it ranks by that score like any fuzzy
match. Among suggestions without a score the plugin's order holds.

`complete` is an optional field in the sense of decision 9, kind 1: no version and no
capability. The SDK sends it whatever version the host agreed to, since a host that ignores
it loses only Tab. It must be text. The host reads an item whose `complete` is not text as
unreadable and leaves out that item alone, and the SDK answers it with a `plugin_error`
naming the item.

`icon` is what the row shows beside its text, in one of two kinds:

| Icon | Shape | The window shows |
|---|---|---|
| path | `{"kind": "path", "path": "/Applications/Safari.app"}` | the icon the system shows for whatever sits at that absolute path: an application bundle's own icon, a document's type icon, a folder |
| symbol | `{"kind": "symbol", "name": "globe"}` | the system symbol of that name, drawn in the row's text colour |

A path must be absolute. A path that does not exist, or a symbol name the system does not
know, leaves the row without an icon and is never an error, so a plugin may name an icon
without checking first. The host may keep a resolved icon for its own lifetime, so an
application whose icon changed shows the new one after the launcher restarts. An icon the
host cannot read, of a `kind` it does not know or of a known kind in the wrong shape,
leaves that row without an icon and costs nothing else. A new kind still needs a new
version, and the SDK refuses to send one the agreed version lacks.

### Effect

What the host does after `run`. The plugin returns it, the host performs it.

| Effect | Shape | The host |
|---|---|---|
| close | `{"kind": "close"}` | hides the launcher |
| copy | `{"kind": "copy", "text": "4"}` | puts the text on the clipboard, then hides |
| open | `{"kind": "open", "target": "https://..."}` | opens the URL or path with the system handler, then hides |
| show | `{"kind": "show", "text": "..."}` | keeps the launcher open and shows the text |

A plugin may also do its own work inside `run`, such as toggling a setting, and then return
`close`.

An effect of a kind the host does not know fails the whole answer, reported as not a
protocol message: the host never guesses at what a plugin asked it to do. A new effect
kind needs a new version.

The host hands an `open` target to the system as given, so a file or an application is sent
as a `file://` URL (`Path.as_uri()` in Python), with its scheme and percent-encoding; a bare
path has no scheme for the system to dispatch on.

## Tasks

A plugin that works between calls (an outbox retrying, an index being built, a cache
refresh) reports it as a **task**, and the host keeps the latest state of each (decision
12). It is the one message a plugin starts. It is a line with an `event` key and no `id`,
written whenever the plugin likes, between calls or in the middle of one:

```json
{"event": "task", "params": {"id": "index", "label": "Indexing notes", "state": "running", "done": 120, "total": 900, "detail": "meetings/2026"}}
```

| Field | | |
|---|---|---|
| `id` | required | Names the task within the plugin, so a later line replaces an earlier one |
| `label` | required | Short text for the person |
| `state` | required | `running`, `done` or `failed` |
| `done`, `total` | optional | Whole numbers of 0 or more, given together, with `done` at most `total`. With neither, there is no progress to show |
| `detail` | optional | Text, one line |

**The capability.** A plugin sends the line only to a host that named `tasks` in the
`capabilities` of `describe`, and sends nothing to one that did not. The protocol stays at
1: the plugin has the choice not to send, which is what makes this a capability and not a
version (decision 9, third kind).

**What the host does with a line.** The reader of the plugin's stdout sorts each line as
it arrives, not when a call asks: a line with an `event` and no `id` is an event, and
any other line goes to the call in flight as before (a line that is neither JSON nor an
event is still reported as not a protocol message). So an event never fails a call and a
call never waits for one. The host:

- cleans the text of `id`, `label` and `detail` (control characters out, cut at 160
  characters) and checks the shape above. A line it cannot use, a task without a `label`
  or a `state`, a `done` above `total`, an event of another name, is dropped and
  noted for that plugin like any other trouble with it. It never fails a call, and the
  notes for one plugin are limited so a loop of bad lines cannot fill the window.
- keeps the latest state per task `id` per plugin, and tells the window about a task
  whose state changed as a `Task` event, at most every 50 ms. A flood of lines costs the
  reading of them and one report per task. The host keeps at most 64 tasks per plugin; a
  new one over that replaces a `done` one, or is dropped and noted.
- forgets a plugin's tasks when the plugin starts again, after a crash, a hang or a
  change to its files. A plugin reports again after `describe`.

What the window shows, and for how long, is the window's business: `running` until
replaced, `done` briefly, `failed` until dismissed.

**In the SDK**, `report(Task(...))` may be called from any thread. It writes its line
under the same lock `serve` takes for answers, so lines never interleave. It does nothing,
without error, before the host's `describe` or when the host did not name `tasks`. A
`running` report of one task is sent at most twice a second (a report inside the
half second is dropped, not held back, so the last `running` update may never be sent);
a change of state, `done` and `failed` are always sent. A task that cannot be carried
raises `InvalidTaskError` to the caller, whatever the host is.

## Notifications

A plugin that watches something (a ticket changing status, a build finishing) tells the person
with a **notice** (decision 13). It is the second line a plugin starts: an `event` key and no
`id`, written whenever the plugin likes, and read by the same reader as a task report:

```json
{"event": "notify", "params": {"id": "PROJ-12", "title": "PROJ-12 moved", "body": "In Review", "open": "https://example.test/PROJ-12"}}
```

| Field | | |
|---|---|---|
| `id` | required | Names the thing within the plugin: a later notice with the same `id` replaces the earlier one in the recent list |
| `title` | required | Short text for the person |
| `body` | optional | Text, a second line |
| `open` | optional | A target the host opens when the person chooses the notice, as it opens an `Open` effect: text, not empty. The host applies no policy to it here |

**The capability.** A plugin sends the line only to a host that named `notify` in the
`capabilities` of `describe`, and sends nothing to one that did not. Like `tasks`, it is a
capability and not a version because the plugin has the choice not to send (decision 9,
third kind, with decision 12's exception). With a host that did not name it, the plugin
reports nothing, and the recent list is then the only place to see what moved. `tasks` and
`notify` are independent: naming one says nothing of the other.

**What the host does with a line.** It sorts the line as it arrives, like a task report, so
a notice never fails a call and a call never waits for one. The host:

- cleans `id`, `title` and `body` (control characters out, cut at 160 characters, as task
  text) and checks the shape above. A notice without an `id` or a `title`, or with an `open`
  that is not text or is empty, is dropped and noted for that plugin like any other trouble
  with it. `open` is kept as sent, because cutting a target breaks it.
- drops a plugin's notices above a rate: more than 5 in 10 seconds. The excess is dropped, and
  the host makes one note about the plugin for each window of 10 seconds in which it
  dropped, so a bug cannot flood the person with notices or with notes. A plugin should send
  one notice per change, and one summary after a wake with many. The rate is the plugin's, not
  the process's, so a restart does not give it a new allowance.
- passes each notice that is kept to the window as a `Notice` event, in the order the plugin
  sent them. Notices are not coalesced: each is something that happened.
- leaves the rest to the app, which does two things with a `Notice`: it posts a system
  notification (not built yet; the app has a `deliver` function for the purpose), and it
  records the notice in the **recent list**.

**The recent list** holds the last 20 notices across plugins, newest first. A notice with the
same plugin and `id` as one already there replaces it, and moves to the newest place. The
list lives in memory: it is empty when the app starts and gone when it quits. A plugin's
restart does not clear it, because what was delivered is history; unlike a plugin's tasks,
which are cleared. It is pure logic in `cmd-core` (`notice::Recent`), as is the rate limit
(`notice::RateLimit`).

A failing watch (unreachable, unauthorised) is a task that stays until dismissed, not a
notice at every poll.

**In the SDK**, `notify(id, title, body=None, open=None)` may be called from any thread. It
writes its line under the same lock `serve` takes for answers, so lines never interleave. It
does nothing, without error, before the host's `describe` or when the host did not name
`notify`. It does not throttle: the plugin sends one notice per change, and the host drops
what is above 5 in 10 seconds. A notice that cannot be carried (`id` or `title` missing,
empty or not text, `body` or `open` not text, `open` empty) raises `InvalidNoticeError` to the
caller, whatever the host is.

## Routing

The host trims the typed text and looks at its first word.

- If the word matches a plugin's `keyword` (ASCII case ignored), only that plugin is asked,
  and it receives the rest of the text. `calc 2+2` reaches the calculator as `2+2`. The
  keyword alone reaches it with an empty string, which is the moment to show defaults.
- Otherwise every plugin without a keyword is asked, each with the whole text.
- Blank text reaches only the plugins whose description has `home: true`, as the home
  query below. A plugin that did not declare it gets nothing for blank input.

### The home query

When the window opens with an empty input, and when the input becomes empty, the host asks
every plugin that declared `home`, in parallel and whatever its `keyword`, as an ordinary
query with a generation: `{"text": "", "home": true}`. The `home` flag is sent only on this
query and only to such plugins; a typed query carries no `home` param. The answers are
merged by the same rules as any query's and are the window's list until the person types,
which replaces them. Enter and the actions work on a home row as on any other. The Python
SDK passes the query to `Plugin.home()` when the plugin has one, else to `query("")`.

Answers from several plugins are merged into one list: highest score first, items without a
score first of all, and ties keep the plugins' order and then each plugin's own order.

## Timeouts

| Call | Host default |
|---|---|
| describe | 60 s, because the first `uv run` may have to build the environment |
| query | 3 s |
| run | 10 s |

A plugin that misses a deadline is reported in the launcher and not retried. Three missed
deadlines in a row count as a hang: the process is killed and started again as below.
Return quickly and do slow work in `run`.

## Lifecycle

Plugins start when the launcher starts and stay running until it exits, each on its own
worker thread, so a slow plugin delays only its own answers. The window is on screen
before the first `describe` and says which plugins are still starting; one that cannot be
started is reported there as soon as its handshake fails. A plugin whose process has
gone (it exited, or its pipe broke) has the call in hand answered with that fact, is
started again with back-off (2 s, doubling to 30 s, forgotten after a healthy call), and
the window says "started again". A plugin that hangs, timing out three calls in a row,
is treated the same way. A change to any file under the plugin's directory, other than
hidden files, `__pycache__` and `uv.lock`, starts it again on the new code and the
window says "reloaded"; the manifest is read again too, so a changed `command` takes
effect. Every restart begins with `describe`, and the new description replaces the old
one; the plugin's tasks are cleared, and it reports them again. Its notices are not: those
already delivered are history, and stay in the recent list. A plugin that cannot be started
again, or started at all, is reported in the window, and the old process keeps answering
while a reload fails.

## Errors

| Code | Who | Meaning |
|---|---|---|
| `bad_request` | SDK | The host sent a line the SDK could not read, such as a `describe` whose `capabilities` is not a list of names. `id` is the request's own, or 0 when the line had none |
| `unknown_method` | SDK | The host sent a well-formed request for a method the SDK does not have, as a newer protocol might. `id` is the request's own |
| `plugin_error` | SDK | The plugin's own code raised, or returned what the protocol cannot carry: a score that is NaN, an icon path or a `complete` that is not text, a kind the agreed version lacks. `message` names the exception, and for a bad item the item |

Plugins may invent further codes. The host shows `code: message` to the person. An error
whose `id` is 0 answers the request in flight, since the host sends one request at a time.

## A full exchange

```
→ {"id": 1, "method": "describe", "params": {"protocol": 1, "capabilities": ["tasks", "notify"]}}
← {"id": 1, "result": {"name": "calculator", "version": "0.1.0", "protocol": 1}}
→ {"id": 2, "method": "query", "params": {"text": "2 + 2 * 3"}}
← {"id": 2, "result": {"items": [{"id": "8", "title": "8", "subtitle": "Press Enter to copy", "icon": {"kind": "symbol", "name": "equal"}}]}}
→ {"id": 3, "method": "run", "params": {"item": "8", "action": "default"}}
← {"id": 3, "result": {"effect": {"kind": "copy", "text": "8"}}}
← {"event": "task", "params": {"id": "cache", "label": "Refreshing the cache", "state": "done"}}
```

The last line is a plugin's own: a task report, which may come at any moment, here after
the call is over. A notice (`{"event": "notify", "params": {...}}`) is another.

## Golden exchanges

`docs/plugin-protocol.golden.json` holds exchanges both sides are tested against: a
`describe` from a version 1 host and from a version 0 one, a query answered with items with
and without icons of both kinds, a `describe` with `home` and the home query, with scores in and out of range, with an icon of an
unknown kind and with an item the host cannot read, a run, and an error. Each holds the
request, the answer, and what the host reads from the answer. `crates/cmd-core/tests/golden.rs`
checks that the host sends the requests and reads the answers as written there, and
`python/cmd-sdk/tests/unit/test_golden.py` that the SDK reads the requests and writes the
answers. A plugin in another language can test itself against the same file.

The same file holds `events`, the lines a plugin starts: a task running, done and failed,
text that the host cleans, lines it drops and notes (no label, `done` above `total`, an
unknown state, an event of another name), and lines that are not events at all (an answer,
a line with both an `event` and an `id`). It also holds notices: with and without a body
and a target, text the host cleans, and ones it drops and notes (no title, an empty target).
Each holds the line and what the host reads from
it; the SDK writes the lines it can as written and refuses the rest. The host side is
`cmd-core`'s `task::classify`, a pure function the reader thread calls on each line, and
`crates/cmd-host/tests/calculator.rs` also drives a task and a notice from the real SDK
through the real host.

## Writing one in Python

`python/cmd-sdk/README.md`. A plugin is a `Description`, a `query` function and a `run`
function; `serve` does the rest.
