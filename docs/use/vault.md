# The vault plugin

Capture a to-do or a note into Obsidian from the launcher, and search the vault. The
plugin reaches Obsidian only through the obsidian CLI, and a capture goes to an outbox
first, so nothing is lost while Obsidian is closed or slow. Decision 10 is the design.

!!! warning "Not yet checked against the real CLI"
    The plugin is tested against a fake obsidian CLI. The command names it uses
    (`daily:append`, `append`, `create`, `read`, `daily:read`, `search`, `open`, with
    `key=value` parameters and a leading `vault=<name>`) are guesses until the CLI spike
    (TASK-2.4) runs on a Mac. They all live in `plugins/vault/src/vault/invocations.py`.

## What it does

| You type | You see | Enter |
|---|---|---|
| `todo call Sam` | the line it will write, and where | queues it and closes; the plugin writes it |
| `note Priya wants the plan` | the line, with the time it was captured | queues it and closes |
| `find budget` | notes that match, while Obsidian runs | opens the note |
| `vault` | whether Obsidian runs, every config problem, every capture still waiting | depends on the row |

Every keyword comes from the config; `todo`, `note` and `find` are the examples below. The
`open` kind of capture (a `1:1` that makes a person's note from a template) and the
`tasks` view are accepted by the config and not built yet: their keyword shows a row that
says so.

Typing never starts Obsidian. A capture's row is built from the config alone; a search
calls the CLI only when Obsidian is running, with a deadline of `deadlines.query` seconds.

## The config

`config.toml` in the plugin's config directory (`~/Library/Application Support/cmd/plugin-config/vault/`).
The plugin reads it once at start; saving it restarts the plugin. The smallest that works:

```toml
[obsidian]
bin = "/usr/local/bin/obsidian"

[[capture]]
keyword = "todo"
kind = "append"
target = "@daily"
```

A fuller one:

```toml
status_keyword = "vault"
date_format = "%Y-%m-%d"
time_format = "%H:%M"

[obsidian]
bin = "/usr/local/bin/obsidian"
vault = "Work"

[obsidian.deadlines]
probe = 0.3
query = 1.5
write = 5.0
run = 2.0

[[capture]]
keyword = "todo"
kind = "append"
target = "@daily"
heading = "Tasks"
line = "- [ ] {text}"

[[capture]]
keyword = "note"
kind = "append"
target = "Inbox.md"
heading = "Captured"
line = "- {time} {text}"

[[view]]
keyword = "find"
kind = "search"
```

| Key | Must be set | Default | Rule |
|---|---|---|---|
| `status_keyword` | no | `"vault"` | one word |
| `date_format`, `time_format` | no | `"%Y-%m-%d"`, `"%H:%M"` | strftime formats for `{date}` and `{time}` |
| `obsidian.bin` | yes | none | absolute path to the CLI; there is no default, since a Dock launch has a bare `PATH` |
| `obsidian.app` | no | `"/Applications/Obsidian.app"` | what "Obsidian is not running" opens |
| `obsidian.process` | no | `"Obsidian"` | the process name `pgrep -x` looks for |
| `obsidian.vault` | no | the CLI's default vault | the vault every call names |
| `obsidian.deadlines.probe` | no | `0.3` | seconds; `probe + query` at most 1.8 |
| `obsidian.deadlines.query` | no | `1.5` | seconds a search may take |
| `obsidian.deadlines.write` | no | `5.0` | seconds a write may take, at most 30 |
| `obsidian.deadlines.run` | no | `2.0` | seconds opening a note may take, at most 8 |
| `capture.keyword` | yes | | one word, unique among every keyword, case ignored |
| `capture.kind` | yes | | `append`; `open` is accepted and not built yet |
| `capture.target` | yes | | `@daily` (today's daily note) or a vault path ending `.md`, which may use `{text}` and `{date}` |
| `capture.template` | no | none | a core template by name, used when the target is created; not with `@daily` |
| `capture.heading` | no | the end of the note | the heading the line goes under, without `#` |
| `capture.line` | no | `"- {text}"` | one line holding `{text}`; may use `{date}` and `{time}` |
| `view.keyword` | yes | | as `capture.keyword` |
| `view.kind` | yes | | `search`; `tasks` is accepted and not built yet |
| `view.limit` | no | `20` | rows, 1 to 50 |

A key the schema does not have, a placeholder it does not know, and a config with no
capture and no view are errors, each shown as a row under `vault` and on its keyword. A bad
capture is dropped and the rest work; a bad deadline uses its default. With no config at
all, `vault` says where to create one and Enter opens that directory. A config that does
not parse shows the parser's message on `vault` and on the keywords of the last config
that did.

## The outbox

Each capture is a file in the plugin's data directory (`outbox/<id>.json`) until the CLI
has written it. A thread writes the oldest first, one at a time, and only while Obsidian
runs, so a capture made while it is closed waits as long as it takes and costs nothing.
A failed write is tried again 5 s, 30 s, 2 min and 10 min later; the fifth failure stops
and waits for you. A write killed at its deadline may have landed, so before writing it
again the plugin reads the note and, if the line is there, counts it as written.

Waiting captures show under your keywords (three at most) and all of them under `vault`:

| Row | Means | Actions |
|---|---|---|
| Waiting | not written yet: Obsidian is closed, or a try failed and the next is due at the time shown | Retry now (after a failure), Copy, Discard |
| Writing | a call is in flight | Copy |
| Checking | a write may have landed; the next try reads the note first | Retry now, Copy, Discard |
| Not written | five tries failed | Retry, Copy, Discard |

`@daily` is the daily note of the day the CLI writes it: a to-do captured on Monday
evening while Obsidian is closed lands in Tuesday's note if that is when Obsidian opens.
