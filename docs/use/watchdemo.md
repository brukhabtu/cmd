# The watchdemo plugin

Watch tickets that move, from the launcher, without a network or an account. The tickets
are a JSON file you edit by hand; the plugin reads it every few seconds and tells you when a
ticket you watch changes status. It is the demonstration of decision 13 (watchers, Tab to
complete, notices and the home list), and the same shape serves a real tracker once
something other than a file feeds it.

!!! warning "Notifications do not reach macOS yet"
    The plugin sends a notice to the host when a ticket moves, and the host keeps the last
    twenty in its recent list. Posting a macOS notification is TASK-6.4 and is not built, so
    until it is, **the place to see that something moved is the home list** (open the
    window with an empty input). The plugin also needs a host that names the `notify`
    capability; one that does not is sent nothing, and the home list still shows the change.

## What it does

| You type | You see | Enter | Tab |
|---|---|---|---|
| `watch` | every ticket, then a "Watching (N)" suggestion | the ticket's first action | completes the selected row |
| `watch login` | tickets whose id or title contains it, the closest first | opens the ticket | completes it |
| `watch PROJ-12 ` | that ticket alone (an id and a space) | watches it, or unwatches it | |
| `watch watching` | the tickets you watch, each with its status now | opens the ticket | completes it |
| nothing (the window opens) | what moved, newest first, then what you watch | | |

A ticket row has three actions. The first is **Open**, which goes to the ticket's `url`; a
ticket with no `url` has **Copy id** first instead. The second is **Watch**, or **Unwatch**
on one you already watch. The last is **Copy id**. Watching shows a line and keeps the
window open.

!!! note "Only a row's first action is reachable today"
    The window runs the first action on Enter and has no menu for the others yet (Cmd-K is
    DRAFT-6). So that the demo works anyway, a ticket you have narrowed to, by Tab or by
    typing its id and a space, puts **Watch** (or **Unwatch**) first: Tab, then Enter. In
    any longer list Open is first. Open and Copy id on a narrowed ticket wait for the menu.

## Try it

It works out of the box: no file to write and no config.

1. Install it and open cmd again (a new plugin starts the next time cmd starts):

    ```sh
    cmd plugin install watchdemo
    ```

    From a clone of this repository, `cmd plugin install ./plugins/watchdemo` does the same.

2. Type `watch`. Three sample tickets (DEMO-1, DEMO-2 and DEMO-3) are there, from a file the
   plugin made in its data directory.

3. Type `watch DEMO-2`, press Tab (the input becomes `watch DEMO-2 `) and Enter: that is
   **Watch**. The plugin has noted it as `In Review`.

4. Type `watch` again and choose **Move a watched ticket on (demo)**. That changes
   DEMO-2's status in the sample file, the way a tracker would change under you. Within
   `interval` seconds the plugin notices. Open the window with an empty input: the first row
   is `DEMO-2: In Review -> Done`, with the time it was seen. Once macOS notifications exist
   (TASK-6.4) the same change is a notification titled "DEMO-2 moved".

Move it on again and it goes round: Open, In Review, Done, Open. **Edit the sample tickets**
opens the file, so you can add your own or change a status by hand. The plugin never
overwrites that file.

Several things are worth trying: `watch watching`; Unwatch DEMO-2 (Tab, Enter) and move
tickets on again (nothing is told); stop and start cmd and move one on (a change is told
once, and the watch survives).

### Watching your own file

To watch a file of your own instead, write the tickets anywhere you like:

```json
[
  {"id": "PROJ-12", "title": "Fix the login page", "status": "Open",
   "url": "https://example.test/PROJ-12"},
  {"id": "PROJ-13", "title": "Login emails bounce", "status": "In Review"}
]
```

`id`, `title` and `status` are required text; `url` is optional. Ids must be unique. A file
that is not a list of such objects is an error you will see (below), not a crash. Then
point the plugin at it with a `config.toml` in
`~/Library/Application Support/cmd/plugin-config/watchdemo/`, which you create:

```toml
tickets = "/Users/you/tickets.json"
interval = 5      # seconds between reads; optional, 5 by default, never below 0.5
```

Saving the file restarts the plugin. The sample rows go away, because the file is yours.

## What is told, and what is not

- Only tickets you watch are told. The first time the plugin sees a watched ticket it
  records the status and says nothing; a change after that is one notice, "PROJ-12 moved",
  `In Review -> Done`.
- A ticket that disappears from the file keeps its place in the list (`watch watching`
  shows "not in the tickets file", and Unwatch drops it); if it comes back at a new status,
  that is a change.
- After the Mac has slept, or the plugin was stopped, for more than three intervals, and
  more than three tickets moved meanwhile, you get one notice, "N tickets moved", naming
  the first few. Each is still on the home list.
- The list of changes holds the last fifty.

## When something is wrong

- **The config is not TOML, or `tickets` is not a path:** `watch` shows a row saying what
  to set, and the window's blank input shows the same. Nothing is polled. (No `tickets` at
  all is not a fault: the sample file is used.)
- **The tickets file is missing, not JSON, or not a list of tickets:** the rows say which
  and name the file, and the plugin reports one task, "Tickets file", as failed on the
  status line. It is reported once, not at every read, and marked done when the file reads
  again. No notice is sent for it.
- **The saved state is damaged:** the plugin sets `state.json` aside as
  `state.json.corrupt` in its data directory
  (`~/Library/Application Support/cmd/plugin-data/watchdemo/`), starts with nothing
  watched, and says so once in its log and on the blank-input list.

## Design

Decision 13. The plugin is a pure core (`tickets`, `options`, `state`, `diff`, `rows`)
with a thin shell (`keeper` for the file, `poller` for the thread, `plugin` for the
protocol); the diff is a function from the old state, the tickets just read and the
watched set to the changes and the new state, so it is tested without threads or files. The
polling thread is a daemon that calls `cmd_sdk.notify` and `cmd_sdk.report`; the host does
not schedule polls. State is written to a temporary file and renamed into place.
