# Plugin protocol, version 0

How the launcher talks to a plugin. The Rust side is `crates/cmd-core/src/protocol.rs`, the
Python side is `python/cmd-sdk/src/cmd_sdk/protocol.py`, and
`crates/cmd-host/tests/calculator.rs` proves the two agree by driving the real calculator
plugin. A change to the protocol changes all three in one commit.

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

Where the host looks for plugin directories is the host's business: the per-user directory
(`~/Library/Application Support/cmd/plugins` on macOS), `./plugins` under the working
directory when it exists, or the directories in `CMD_PLUGINS` when that is set.

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
| `describe` | `{"protocol": 0}` | Description | Once, right after the process starts |
| `query` | `{"text": "..."}` | `{"items": [Item]}` | On every change to the typed text that reaches this plugin |
| `run` | `{"item": "...", "action": "..."}` | `{"effect": Effect}` | When the person presses Enter on one of this plugin's items |

### Description

```json
{"name": "calculator", "version": "0.1.0", "protocol": 0, "keyword": "calc"}
```

`protocol` is the version the plugin speaks. The host refuses a plugin whose version differs
from its own and says so. `keyword` is optional; see Routing.

### Item

```json
{
  "id": "4",
  "title": "4",
  "subtitle": "Press Enter to copy",
  "score": 0.8,
  "actions": [{"id": "copy", "title": "Copy"}]
}
```

`id` is what comes back in `run`. `subtitle`, `score` and `actions` are optional.

`score` is a confidence between 0 and 1 for a fuzzy match. Leave it out for a definite
answer: the host ranks an item without a score above every item with one, so a calculator's
`4` sits above an application whose name happens to contain a 4.

`actions` are what Enter can do. The first is the default. With no actions the host sends
`run` with action `"default"`.

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

A plugin that misses a deadline is reported in the launcher and not retried. Return quickly
and do slow work in `run`.

## Lifecycle

Plugins start when the launcher starts and stay running until it exits, each on its own
worker thread, so a slow plugin delays only its own answers. A plugin whose process has
gone (it exited, or its pipe broke) has the call in hand answered with that fact, is
started again with back-off (2 s, doubling to 30 s, forgotten after a healthy call), and
the window says "started again". A change to any file under the plugin's directory,
other than hidden directories and `__pycache__`, starts it again on the new code and the
window says "reloaded". A plugin that cannot be started again is reported in the window.
A plugin that hangs is not restarted today; each call times out instead.

## Errors

| Code | Who | Meaning |
|---|---|---|
| `bad_request` | SDK | The host sent a line the SDK could not read. `id` is 0 when the line had no id |
| `plugin_error` | SDK | The plugin's own code raised. `message` names the exception |

Plugins may invent further codes. The host shows `code: message` to the person. An error
whose `id` is 0 answers the request in flight, since the host sends one request at a time.

## A full exchange

```
→ {"id": 1, "method": "describe", "params": {"protocol": 0}}
← {"id": 1, "result": {"name": "calculator", "version": "0.1.0", "protocol": 0}}
→ {"id": 2, "method": "query", "params": {"text": "2 + 2 * 3"}}
← {"id": 2, "result": {"items": [{"id": "8", "title": "8", "subtitle": "Press Enter to copy"}]}}
→ {"id": 3, "method": "run", "params": {"item": "8", "action": "default"}}
← {"id": 3, "result": {"effect": {"kind": "copy", "text": "8"}}}
```

## Writing one in Python

`python/cmd-sdk/README.md`. A plugin is a `Description`, a `query` function and a `run`
function; `serve` does the rest.
