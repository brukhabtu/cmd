---
id: decision-10
title: 'The vault plugin''s config, outbox and query path'
date: '2026-10-08 20:31'
status: proposed
---
## Context

Task 2 wants a launcher that captures into Obsidian: `todo <text>` into today's daily
note, a `note`, and `1:1 <person>` that creates or opens a person's note from a core
template, with no vault-specific value in the code and nothing lost while Obsidian is
closed. Decision 9 gave the vault plugin its rules: it reaches Obsidian only through the
obsidian CLI at an absolute path from its config, a call in `query` has a deadline shorter
than the host's 3 s and never launches Obsidian, and a write goes to an outbox in the data
directory and is retried by the plugin's own thread. It left this task the config schema,
the outbox's states, retries and duplicate rule, and how the plugin matches its keywords
until the protocol carries several (draft 5).

**Task 2.4, the spike on how the CLI behaves, has not run.** It needs the owner's Mac. This
decision guesses none of its answers. The config schema and the outbox are the same
whichever way each answer goes; the places where an answer changes a number or a branch
are marked **[2.4]** and gathered in the table at the end of the Decision.

## Decision

### The config

The plugin reads `config.toml` in its config directory once, at start, through the SDK's
`config()` (task 2.6). A change to the file restarts the plugin (decision 9), so the
query path never reads or checks it. A full example, which carries one capture of each
kind the intent names and both views:

```toml
status_keyword = "vault"
date_format = "%Y-%m-%d"
time_format = "%H:%M"

[obsidian]
bin = "/usr/local/bin/obsidian"
app = "/Applications/Obsidian.app"
process = "Obsidian"
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

[[capture]]
keyword = "1:1"
kind = "open"
target = "People/{text}.md"
template = "Person"

[[view]]
keyword = "find"
kind = "search"

[[view]]
keyword = "tasks"
kind = "tasks"
limit = 30
```

The smallest config that works:

```toml
[obsidian]
bin = "/usr/local/bin/obsidian"

[[capture]]
keyword = "todo"
kind = "append"
target = "@daily"
```

The `bin` above is an example: where the CLI sits on disk is for the spike to record
**[2.4]**, and there is no default, because a Dock launch has a bare PATH and a guess would
fail quietly.

| Key | Must be set | Default | Rule |
|---|---|---|---|
| `status_keyword` | no | `"vault"` | one word; the plugin's own view of its config and outbox |
| `date_format`, `time_format` | no | `"%Y-%m-%d"`, `"%H:%M"` | strftime formats for `{date}` and `{time}` |
| `obsidian.bin` | yes | none | absolute path to an executable file |
| `obsidian.app` | no | `"/Applications/Obsidian.app"` | absolute; what "Open Obsidian" opens |
| `obsidian.process` | no | `"Obsidian"` **[2.4]** | the exact process name the probe looks for; the spike records what `pgrep -x` sees |
| `obsidian.vault` | no | none, so the CLI's own default vault | when set, every call names this vault **[2.4]** how |
| `obsidian.deadlines.probe` | no | `0.3` | seconds, above 0 |
| `obsidian.deadlines.query` | no | `1.5` **[2.4]** | seconds, above 0; `probe + query` at most 1.8, since the call can wait up to 1 s more for pipes a grandchild holds open, and the three together stay under the host's 3 s |
| `obsidian.deadlines.write` | no | `5.0` **[2.4]** | seconds, above 0 and at most 30; a call on the outbox thread |
| `obsidian.deadlines.run` | no | `2.0` | seconds, above 0 and at most 8; the longest `run` spends waiting on the CLI |
| `capture.keyword` | yes | | one word; unique among every keyword here, ASCII case ignored |
| `capture.kind` | yes | | `append` (add a line to a note) or `open` (create the note if missing, then open it) |
| `capture.target` | yes | | `@daily`, today's daily note, for `append` only; or a vault-relative path ending `.md` that may use `{text}` and `{date}` |
| `capture.template` | no | none | an Obsidian core template by name, used when the target is created; not with `@daily`, which uses the Daily notes template |
| `capture.heading` | no | none, so the end of the note | `append` only; heading text without `#`; the line goes at the end of that section |
| `capture.line` | no | `"- {text}"` | `append` only; one line that contains `{text}`, and may use `{date}` and `{time}` |
| `view.keyword` | yes | | as `capture.keyword` |
| `view.kind` | yes | | `search` (notes matching the text) or `tasks` (open tasks matching the text) |
| `view.limit` | no | `20` | rows, 1 to 50 |

`{text}` is what follows the keyword. Put into a path, it loses the characters Obsidian
refuses in a file name (`\ / : * ? " < > | # ^ [ ]`) and its outer spaces. A key the
schema does not have, a placeholder it does not know, and a config with no capture and no
view are all errors, so a misspelt key is seen rather than ignored.

A config problem is a row, never an exception, and never stops what still works:

| Problem | The plugin | The person sees |
|---|---|---|
| no `config.toml`, or an empty one (`config()` returns `{}` for both) | starts with no captures | on `vault`: "No config: create config.toml in <directory>"; Enter opens the directory |
| it does not parse, is a directory or cannot be read (`config()` raises `ConfigError`, whose message holds the path and the parser's own text, line and column included) | starts with no captures | that message, on `vault` and on each keyword of the last config that parsed (kept in the data directory as `keywords.json`), with "nothing is captured until this is fixed" |
| a capture or view is invalid | drops that one; the rest work | "<keyword>: <problem>" on its keyword, when it has one, and on `vault` |
| `obsidian.bin` is not an absolute, executable file | captures still queue and wait | the problem, on every keyword |
| a deadline is out of range | uses that deadline's default | the problem, on `vault` |
| the SDK cannot find the config or data directory | starts with no captures | the SDK's message naming the variable, on `vault` |

### Keywords until draft 5

The plugin declares no `keyword` in `describe`, so the host sends it every text whose first
word is no other plugin's keyword, whole. The plugin trims the text, takes the first word
up to whitespace, and compares it, ASCII case ignored as the host does, with
`status_keyword` and every capture and view keyword. **A first word that is not one of
them gets `{"items": []}` at once**, with no file read, no probe and no CLI call, since this
branch runs on nearly every keystroke. A keyword's argument is the rest, trimmed. A
keyword another plugin declares (`f`, `web`) never reaches this plugin; draft 5 reports
such clashes.

### The query path

- **It never raises.** The handler's body is one `try`; any exception becomes one row,
  "vault: <exception>: <message>", and goes to stderr.
- **Captures never call the CLI.** A capture's row is built from the config, the outbox in
  memory and the probe's answer: no CLI call and no file read.
- **It never launches Obsidian.** The only outside calls are the probe and, for a view,
  the CLI's `search` or `tasks`, made only after the probe said Obsidian is running.
- **Every call has a deadline under the host's.** The probe is `/usr/bin/pgrep -x
  <process>` with the `probe` deadline: exit 0 is running, anything else or a timeout is
  not running. A view's CLI call has the `query` deadline. Both go through the SDK's
  call (task 2.6) with `kill_on_timeout=True`, which kills the child and what it started
  at its deadline, and captures its stdout and stderr. After a normal exit the call can
  wait up to 1 s more for pipes a grandchild holds open, so the probe, the view's call
  and that grace together stay under the host's 3 s (hence `probe + query` at most 1.8).
  The call raises `OSError` when `bin` does not exist or will not run: `query` shows it as
  a row, and the outbox thread counts it as a failed call. The probe's answer is kept 2 s, a
  search's answer 10 s per text, and the task list 30 s, filtered for each keystroke in
  the plugin. **[2.4]** row 1 can move views off the query path altogether.
- **A closed Obsidian** shows on a capture's row as the subtitle's end, "Obsidian is not
  running: kept until it opens", and as a view's only row, "Obsidian is not running",
  whose Enter opens `obsidian.app`. A running Obsidian that misses the deadline shows
  "Obsidian did not answer within 1.5 s"; a CLI error shows the first line of its stderr
  **[2.4]** (that errors arrive on stderr, and in what form, is a guess until the spike).

A keyword's answer is its own rows, then up to three outbox rows, then "N more: type
vault" if there are more. `vault` shows Obsidian running or not, every config problem and
every outbox entry.

### The worked examples

| Typed | Row in `query` | Enter (`run`) | The outbox thread |
|---|---|---|---|
| `todo call Sam about the offsite` | "- [ ] call Sam about the offsite", subtitle "todo: today's daily note, under Tasks" | queues the line for `@daily` and returns `close` | appends the line to today's daily note under Tasks (`daily:append`) |
| `note Priya wants the hiring plan by Friday` | "- 14:30 Priya wants the hiring plan by Friday", subtitle "note: Inbox.md, under Captured" | queues it for `Inbox.md` and returns `close` | creates `Inbox.md` if missing (no template, so empty), then appends the line under Captured (`create`, `append`) |
| `1:1 Sam Lee` | "1:1: Sam Lee", subtitle "Opens People/Sam Lee.md, made from template Person if missing" | queues the create; returns `close` once the note is open, or after the `run` deadline; with Obsidian closed, returns `open` on `obsidian.app` to start it | if the note is missing, creates it from Person (`create`); then opens it if the entry is under 60 s old |
| `todo` alone | "todo <text>", subtitle "Adds a to-do to today's daily note" | `show`: "Type the to-do after todo" | nothing |

`{time}` and `{date}` are filled when the capture is queued and never again. `@daily` is
the daily note of the day the CLI writes it, so a to-do captured on Monday evening while
Obsidian is closed lands in Tuesday's note if that is when Obsidian opens.

### The outbox

Every capture is queued: an `append` capture's line and an `open` capture's create. A view,
opening a search result and the outbox's own actions are not.

Each entry is one JSON file, `<data>/outbox/<id>.json`, written whole to a temporary name,
flushed with fsync and renamed, so an entry is all there or not there. The id is the local
capture time and six random hex digits, so the names sort oldest first:

```json
{"id": "20261008T143005-3f9a1c", "created": "2026-10-08T14:30:05+01:00",
 "keyword": "todo", "kind": "append", "target": "@daily", "template": null,
 "heading": "Tasks", "line": "- [ ] call Sam about the offsite",
 "state": "pending", "attempts": 0, "next_try": "2026-10-08T14:30:05+01:00",
 "last_error": null, "open_until": null}
```

The files are the truth at start; the plugin then holds them in memory behind one lock,
which `query` reads and `run` and the thread change.

| State | Means | Goes to |
|---|---|---|
| `pending` | saved and waiting for its next try, which for a new entry is now | `writing`, when it is due and Obsidian is running |
| `writing` | a CLI call for it is in flight | gone (written); `pending` (the call failed and tries remain); `unknown` (the call was killed at its deadline); `failed` (the fifth failed call) |
| `unknown` | the call was killed at its deadline, or the plugin stopped mid-call, so the write may have landed | gone (the check found it landed); `writing` (the check found it had not); `unknown` again, with the next try later (the check itself failed or was killed); `failed` (the fifth try, a check counting as one) |
| `failed` | no tries remain | `pending` on Retry; gone on Discard |
| gone | written, or discarded: the file is deleted | |

At start, an entry found in `writing` becomes `unknown`.

**Durable first.** A change of state is written to the entry's file, the same way (a
temporary name, fsync, rename), before the call it announces. `writing` is on disk before
the CLI is called, so a crash after the CLI succeeded and before the file was deleted
restarts the entry as `unknown`, and the check finds the line. An entry is deleted only
after the call returned success or the check found the line.

**Retries.** One thread, which the plugin starts at start, is the only code that calls the
CLI to write. It takes the oldest due entry, one at a time, so two captures to one note
land in the order they were made. An entry is due when its `next_try` has passed and the
probe says Obsidian is running. The thread wakes when `run` queues an entry, when the
person presses Retry, at the soonest `next_try`, and every 10 s while an entry waits for
Obsidian; with an empty outbox it sleeps until woken. A try counts only when the CLI was
called, so a closed Obsidian costs nothing and a capture waits for it as long as it takes.
After a failed or killed call the next try comes 5 s, 30 s, 2 min, then 10 min later; the
fifth failed call makes the entry `failed`. These numbers live in the code. **[2.4]** If
the CLI's exit codes tell a lasting error (an unknown template) from a passing one, a
lasting error goes to `failed` at once.

**The duplicate rule.** The line is rendered once, when queued, so every try writes exactly
the same text. Before an `unknown` entry is written again, the thread reads the target
through the CLI **[2.4]** (which command reads a note, and today's daily note): for
`append`, if the note holds the entry's line as a whole line, the entry is written and
gone; for `open`, if the note exists, the create is skipped. An `open` entry is checked
this way before every create, not only after a timeout. A check that fails or is killed
counts as a try and leaves the entry `unknown`. Two known gaps, accepted: the same line
captured twice into one note, the second write timing out, counts as written, though the
note already holds that line; and for `@daily`, a check that runs after midnight reads the
new day's note, so the line may be written twice.

**What the person sees.** Outbox rows, ids `outbox:<entry id>`:

| Entry | Title | Subtitle | Actions |
|---|---|---|---|
| `pending`, Obsidian closed | Waiting: <line or target> | <keyword>, <target>: Obsidian is not running | Copy, Discard |
| `pending` after a failed call | Waiting: <line or target> | try <n> of 5 at <time>: <last error> | Retry now, Copy, Discard |
| `writing` | Writing: <line or target> | a call is in flight | Copy |
| `unknown` | Checking: <line or target> | <last error, or: checking whether it landed> | Retry now, Copy, Discard |
| `failed` | Not written: <line or target> | <last error> | Retry, Copy, Discard |

Retry sets the entry `pending` with no tries used and `next_try` now. Copy returns `copy`
with the line, or the target's path for `open`, so nothing is lost even if the person gives
up on the outbox. Discard deletes the file.

**No direct file writes.** The intent's open question, the CLI alone or files as well when
Obsidian is closed, is answered: the CLI alone. A capture made while Obsidian is closed is
kept and seen, which is what the intent asks, and writing under a running Obsidian or a
sync client is a risk this does not need. Revisit only if **[2.4]** row 4 is no and the
wait proves too long in use.

### Where task 2.4 changes this

| The spike finds | Then | Otherwise |
|---|---|---|
| warm `search` and `tasks` answer well inside 1.5 s | views call the CLI in `query` as above; `deadlines.query` defaults to three times the warm 95th percentile, at least 0.5 s and at most 1.5 s | views read caches the plugin's thread refreshes while Obsidian runs; `search` becomes a match on note names from a cached list, and the owner decides whether full-text search moves to Enter |
| a call launches a closed Obsidian | the probe guards every call, in `query` and on the thread | the probe still runs in `query`, for the "not running" row |
| a call hangs while Obsidian is paused | the `unknown` state and the check are met often | the same rules, met rarely |
| the CLI writes while Obsidian is closed, without launching it | the thread drops the probe and drains at once | entries wait for Obsidian, as above |
| `create` takes `content` and `template` together | creating a target from a template and adding the line is one call | two calls; a stop between them is safe, since the check skips the create and then the line |
| a template-made file lands at `path=` | targets with a template work as written | task 2.8 finds the CLI's way to place it (a move after the create); the config does not change |
| `tasks format=json` gives file and line | Enter on a task opens its note at that line | Enter opens the note; toggling a task is not designed here, since a toggle written twice undoes itself |
| `daily:append` creates a missing daily note | `@daily` works as written | `@daily` is refused at start with a row saying to use a path target such as `"Daily/{date}.md"` with the daily template |
| the warm 95th percentile of `append` | `deadlines.write` defaults to three times it, at least 2 s and at most 30 s | |

The spike's list lacks seven things this design needs, which it should answer too: the
process name `pgrep -x` finds for a running Obsidian; whether CLI errors arrive on stderr
and in what form; whether the CLI can open a note, which the `open` kind will need;
whether the CLI can put a line under a heading (if not, `heading` is refused at start with a row
saying to remove it, until the owner chooses another way); which command reads a note and
today's daily note; where the CLI is installed on disk; what `create` does to a path that
exists; and how a call names a vault.

### Assumed, for the owner to confirm

- Three capture keywords are the examples, not the code's: every keyword comes from config.
- `note` appends a timestamped line to one inbox note, rather than making a new note per
  capture; a capture of `kind = "open"` with `target = "Inbox/{date} {text}.md"` covers the
  other reading without a new kind.
- `1:1` opens the note only within 60 s of Enter, so a note made hours later, when
  Obsidian next opens, does not jump onto the screen. Sixty seconds is a guess at a cold
  start of Obsidian, not a measurement.
- With Obsidian closed, Enter on a `1:1` starts Obsidian (`run` may; `query` may not).
  Enter on a `todo` or `note` does not: it queues and closes.
- Outbox rows appear only on the plugin's own keywords, never on other text, so a failed
  capture is seen the next time any vault keyword is typed rather than on every keystroke.
- `config()` is as the SDK has it: `{}` for a missing directory or file, `ConfigError`
  for one that does not parse or cannot be read. The plugin cannot tell a missing file from
  an empty one, and does not need to: both leave it with nothing to capture.
- No direct file writes, as above.

## Consequences

- Task 2.8 builds the `append` kind (`todo`, `note`), the outbox, the `search` view and the
  `vault` view, against the fake CLI. The `open` kind (`1:1`) and the `tasks` view need a
  task of their own, to be filed; the schema already holds them, so no config changes when
  they land.
- Task 2.4 gains the questions above, and its table sets the defaults marked **[2.4]**.
- Task 2.6's call already tells a call killed at its deadline (`timed_out`, no return code)
  from one that exited non-zero, which is what makes an entry `unknown` or `pending`.
- Draft 5 must let `query` say which keyword was typed, or the plugin keeps matching the
  first word itself. When the host names the `keywords` capability, the plugin sends its
  configured keywords; with an older host it keeps the branch above.
- Task 2's open question on the CLI against files is answered here, for the owner to tick.
- The plugin's user page owes this schema, its defaults and its rows, with task 2.8.
