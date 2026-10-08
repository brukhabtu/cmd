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
line on it that is not a protocol message is reported as an error that quotes the line.
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
up is dropped.

## Methods

| Method | Params | Result | When |
|---|---|---|---|
| `describe` | `{"protocol": 1, "capabilities": []}` | Description | Once, right after the process starts |
| `query` | `{"text": "..."}` | `{"items": [Item]}` | On every change to the typed text that reaches this plugin |
| `run` | `{"item": "...", "action": "..."}` | `{"effect": Effect}` | When the person presses Enter on one of this plugin's items |

### Description

```json
{"name": "calculator", "version": "0.1.0", "protocol": 1, "keyword": "calc"}
```

`protocol` is the version the plugin and the host now speak, as agreed below. `keyword` is
optional; see Routing.

### Negotiation

The params of `describe` carry `protocol`, the version the host speaks, and
`capabilities`, a list of names for behaviour the host supports beyond its version. A
missing list is an empty one, as from a host older than the list. This host speaks 1 and
names no capability yet, so it sends `{"protocol": 1, "capabilities": []}`.

The plugin answers with the lower of the host's version and its own, and from then on
sends only what that version and those capabilities allow. The host loads a plugin that
answers any version from 0 to its own, and refuses any other with a message naming the
plugin and the range. It sends a plugin only what the version it answered has. Dropping
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

### How the contract grows

Every change to the contract is one of three kinds (decision 9).

1. **An optional field.** A host that ignores it still does right by the person, so a
   plugin sends it whatever the host is. No new version, no capability. Neither side
   rejects a field it does not know.
2. **A capability.** The plugin must behave differently when the host does not read the
   field. The host names it in `capabilities`, and the plugin uses it only then, falling
   back otherwise. A capability is named only where a plugin has a fallback to choose. The
   first will be `keywords`, for a plugin with several keywords.
3. **A new version.** Anything the host must decode to keep working, or that changes what
   an existing message means: a new effect kind, a new icon kind, a new method, a message
   in a new direction, a field that becomes required or changes meaning.

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
  "icon": {"kind": "symbol", "name": "equal"}
}
```

`id` is what comes back in `run`. `subtitle`, `score`, `actions` and `icon` are optional.

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

## Routing

The host trims the typed text and looks at its first word.

- If the word matches a plugin's `keyword` (ASCII case ignored), only that plugin is asked,
  and it receives the rest of the text. `calc 2+2` reaches the calculator as `2+2`. The
  keyword alone reaches it with an empty string, which is the moment to show defaults.
- Otherwise every plugin without a keyword is asked, each with the whole text.
- Blank text reaches nobody.

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
one. A plugin that cannot be started again, or started at all, is reported in the
window, and the old process keeps answering while a reload fails.

## Errors

| Code | Who | Meaning |
|---|---|---|
| `bad_request` | SDK | The host sent a line the SDK could not read, such as a `describe` whose `capabilities` is not a list of names. `id` is the request's own, or 0 when the line had none |
| `unknown_method` | SDK | The host sent a well-formed request for a method the SDK does not have, as a newer protocol might. `id` is the request's own |
| `plugin_error` | SDK | The plugin's own code raised, or returned what the protocol cannot carry: a score that is NaN, an icon path that is not text, a kind the agreed version lacks. `message` names the exception, and for a bad item the item |

Plugins may invent further codes. The host shows `code: message` to the person. An error
whose `id` is 0 answers the request in flight, since the host sends one request at a time.

## A full exchange

```
→ {"id": 1, "method": "describe", "params": {"protocol": 1, "capabilities": []}}
← {"id": 1, "result": {"name": "calculator", "version": "0.1.0", "protocol": 1}}
→ {"id": 2, "method": "query", "params": {"text": "2 + 2 * 3"}}
← {"id": 2, "result": {"items": [{"id": "8", "title": "8", "subtitle": "Press Enter to copy", "icon": {"kind": "symbol", "name": "equal"}}]}}
→ {"id": 3, "method": "run", "params": {"item": "8", "action": "default"}}
← {"id": 3, "result": {"effect": {"kind": "copy", "text": "8"}}}
```

## Golden exchanges

`docs/plugin-protocol.golden.json` holds exchanges both sides are tested against: a
`describe` from a version 1 host and from a version 0 one, a query answered with items with
and without icons of both kinds, with scores in and out of range, with an icon of an
unknown kind and with an item the host cannot read, a run, and an error. Each holds the
request, the answer, and what the host reads from the answer. `crates/cmd-core/tests/golden.rs`
checks that the host sends the requests and reads the answers as written there, and
`python/cmd-sdk/tests/unit/test_golden.py` that the SDK reads the requests and writes the
answers. A plugin in another language can test itself against the same file.

## Writing one in Python

`python/cmd-sdk/README.md`. A plugin is a `Description`, a `query` function and a `run`
function; `serve` does the rest.
