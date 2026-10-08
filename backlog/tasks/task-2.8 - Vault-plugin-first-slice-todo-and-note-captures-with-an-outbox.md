---
id: TASK-2.8
title: 'Vault plugin, first slice: todo and note captures with an outbox'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 20:59'
labels:
  - size-5
dependencies:
  - TASK-2.7
  - TASK-2.2
  - TASK-2.5
  - TASK-2.6
modified_files:
  - plugins/vault/cmd-plugin.toml
parent_task_id: TASK-2
type: task
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A new plugin under plugins/vault. Captures `todo` and `note` from config, written through the obsidian CLI in `run` only, with an outbox in the data directory so a capture made while Obsidian is closed or past the 10 s limit is kept and retried. `search` through the CLI with the configured query deadline (1.5 s by default, decision 10), only when Obsidian is running. Tested against a fake obsidian executable whose path is configurable. The real CLI check is owed on a Mac.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 todo and note captures are written to the configured target through the CLI, from config alone
- [ ] #2 With the fake CLI closed, slow or failing, the capture stays in the outbox and is written once when it recovers
- [ ] #3 query never raises, never calls the CLI while Obsidian is not running, and returns within the host timeout
- [ ] #4 The check owed on a Mac is recorded on this task
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What was built

`plugins/vault`, decision 10's first slice, as corrected after review (query default 1.5 s, probe + query at most 1.8, `kill_on_timeout=True` everywhere, `unknown` entries with Retry now, Copy and Discard, every state on disk before the call it announces).

- Pure core, each declared in `[tool.pypeeker.import-boundaries]`: `schema` (config.toml to `Settings` and problems; every key, default and range in decision 10's table), `outbox` (the entry, its states, backoff 5 s, 30 s, 2 min, 10 min, failed on the fifth try, the per-try call sequence and the duplicate check), `invocations` (every CLI command and parameter, all marked [2.4], in one file), `answers` (keyword routing, every row, what an id means).
- Shell: `store` (one JSON file per entry: temporary name, fsync, rename; one lock; `writing` becomes `unknown` at start), `gateway` (the SDK's `call` with `kill_on_timeout=True`; `OSError` becomes a refusal; probe cached 2 s, a search 10 s), `worker` (the one thread that writes), `plugin` (start, query, run, main).
- `todo` and `note` (`append` kind) from config alone; `search` view; `vault` status view. The `open` kind and the `tasks` view are parsed and validated, and their keyword shows "<keyword>: a capture of kind 'open' is not built yet" (also on `vault`); Enter shows the same.
- Registered in the root pyproject (workspace via `plugins/*`, mypy_path, pytest testpaths, pypeeker src and allow table) and mkdocs (mkdocstrings path; user page `docs/use/vault.md`, which decision 10 says this task owes).

## Evidence

- `plugins/vault/tests`: 153 tests (unit: schema, outbox, invocations, answers; functional: the plugin against a fake obsidian executable that `obsidian.bin` names, in modes working, closed, failing, slow and landing, with the probe and the clock injected). The vault suite passes twice in one process (no state leakage).
- AC1: `test_a_todo_lands_in_todays_daily_note_under_its_heading`, `test_a_note_creates_its_target_when_missing_then_appends_in_order`, `test_every_value_comes_from_the_config`, `test_the_thread_writes_what_run_queued_without_being_driven`.
- AC2: `test_while_obsidian_is_not_running_nothing_is_called_and_nothing_is_lost`, `test_a_closed_cli_keeps_the_entry_and_it_is_written_once_on_recovery`, `test_a_failing_cli_fails_the_entry_on_the_fifth_try_and_retry_writes_it_once`, `test_a_slow_write_that_did_not_land_is_checked_then_written_once`, `test_a_slow_write_that_landed_is_found_by_the_check_and_not_written_again`, `test_a_note_whose_create_was_killed_is_checked_and_not_created_twice`, `test_an_entry_left_writing_by_a_crash_is_checked_at_start_and_not_written_twice`, `test_writing_is_on_disk_before_the_cli_is_called`.
- AC3: `test_text_that_is_not_a_keyword_gets_nothing_without_a_probe_or_a_call`, `test_while_obsidian_is_not_running_no_keyword_calls_the_cli`, `test_a_capture_row_never_calls_the_cli_even_while_obsidian_runs`, `test_a_slow_search_answers_within_the_host_timeout_with_the_reason`, `test_query_never_raises`.
- `scripts/check.sh`: every step passes (Rust fmt, clippy and tests; ruff; mypy strict; pytest 448; the SDK functional suite twice; pypeeker strict with the vault's four pure modules declared; the cross-import gate; LikeC4; the strict docs build; the plugin manifests; the philosophy tests) except the online index check, which fails on the vault entry alone: its `ref` cannot hold the manifest until this commit is on GitHub (see below). The offline index check passes.
- Through the real host: `cmd-plugin doctor plugins/vault --query "todo hello from doctor" --run "capture:todo hello from doctor"` with the two directories set and a fake CLI. Doctor ends the plugin within milliseconds, which made a real crash case: the line landed and the entry was left `writing`. Two more short-lived starts turned it `unknown` and ran the check (`daily:read`) without a second append; a start that lived 3 s found the line and deleted the entry. The note holds the line once, after one `daily:append`. A start whose probe found no process made no call at all.

## Assumptions (decision 10 silent or this slice's reading)

1. "Written through the CLI in run only" read as "never in query": `run` queues the entry (on disk first) and returns `close`; the outbox thread writes it at once, as decision 10's worked example has it.
2. Search uses the configured `deadlines.query` (default 1.5 s), not the 2 s in this task's text (coordinator's correction).
3. An entry of a kind this slice does not build is validated like any other and kept; its keyword answers with a row saying it is not built yet. Decision 10 has no row for this case.
4. Order: an entry waits while an older entry for the same target is still to be written (a `failed` one holds nothing up), so "two captures to one note land in the order they were made" holds under backoff too. Two captures in one instant are recorded 1 microsecond apart so their random suffixes cannot reorder them.
5. A try at a path target reads it first, and `create` is called only when the read's error says the note is missing. What `create` does to an existing path is unknown [2.4], so the plugin never asks. A fresh `@daily` entry skips the read (`daily:append` is assumed to create the daily note [2.4]).
6. Retry on an `unknown` entry keeps it `unknown` with no tries used, so the check still runs before the write; on `failed` or `pending` it is `pending` with no tries used.
7. A `pending` entry with no tries and Obsidian running reads "Waiting: ...", subtitle "<keyword>, <target>: next in line" (not in decision 10's table).
8. When `probe + query` exceeds 1.8 s, `query` falls back to its default first, then `probe`.
9. A missing and an empty config.toml both give the "No config" row (coordinator's correction 1); so an empty file never says "no capture and no view".
10. With nothing to report, `vault` lists the configured keywords.
11. A lasting CLI error going to `failed` at once is not built: it needs the spike's exit codes.
12. An outbox file that is not an entry is left where it is and named on `vault`.
13. Guesses until the spike (all in `invocations.py`, or `schema.DEFAULT_PROCESS`): the process name for `pgrep -x`; that errors arrive on stderr and a missing note's error says "not found", "does not exist" or "no such"; `vault=<name>` as the first argument; `path=`, `content=`, `heading=`, `template=`, `query=`, `limit=`; `search` prints one vault-relative path a line; `open path=` opens a note.

## Workarounds and things not done

- `plugins/index.toml` lists the vault, as `scripts/tests/test_check_index.py` requires of every plugin, pinned for now to the commit this work branched from. No commit on GitHub holds `plugins/vault/cmd-plugin.toml` yet, so the online index check fails on this one entry until it is re-pinned to the merge commit (the applications plugin's first commit did the same).
- SDK: nothing changed. The plugin names the config directory with `cmd_sdk.locate.directory_from`, since the SDK has no public helper for it, and treats an `OSError` from `config()` like a `ConfigError` (this worktree's SDK lets a directory or an unreadable file through; the main tree's does not).
- This worktree's `call()` waits up to 1 s per pipe for a grandchild after a normal exit (the main tree's change makes it 1 s in all). With the older one a search could, in the worst case, take 0.3 + 1.5 + 2 s. The plugin is correct against the main tree's SDK.

## The check owed on a Mac (AC4)

Not done. On the owner's Mac, with Obsidian and its CLI installed; each step names what its answer changes (decision 10's "Where task 2.4 changes this" table, and the seven questions after it). `W` below is the vault's name.

1. `command -v obsidian`, and `ls -l` on it. Record the absolute path; it goes in `obsidian.bin` (no default).
2. With Obsidian running, then quit: `pgrep -x Obsidian; echo $?`. Exit 0 then 1 confirms `obsidian.process = "Obsidian"`; otherwise set the name `pgrep -lf Obsidian` shows as `DEFAULT_PROCESS` in `schema.py`.
3. With Obsidian quit: `obsidian vault=W daily:read; echo $?`, watching the Dock. Launches Obsidian: the probe must guard every call (already so). Fails fast: note the exit code and whether the message is on stderr (`invocations.first_line`). Writes while closed (try `daily:append content=x`): decision 10 row 4, the thread may drop the probe.
4. Warm, 20 times each: `time obsidian vault=W search query=meeting limit=20` and `... tasks format=json`. The 95th percentile x 3, between 0.5 and 1.5 s, becomes `deadlines.query`; above 1.5 s, views move off the query path (row 1). Record what `search` prints: one path a line or not (`invocations.found_paths`).
5. `obsidian vault=W daily:append content="- [ ] spike" heading=Tasks` on a day with no daily note, then on one whose note has a `# Tasks` section. Creates the note: `@daily` stands (row 8), else refuse `@daily` at start. Line under Tasks: `heading` stands; ignored or refused: refuse `heading` at start with a row.
6. `obsidian vault=W read path=Nope.md; echo $?` and `obsidian vault=W daily:read`. Record the missing-note message; adjust `_MISSING` in `invocations.py`. Confirms which command reads a note and today's daily note (the duplicate check).
7. `obsidian vault=W create path=Spike/A.md template=Person`, then the same again. Where the file lands (row 6), and what `create` does to an existing path (must not overwrite; the plugin never asks it to).
8. `obsidian vault=W append path=Missing.md content=x; echo $?`. An error confirms read-then-create; a silent create means the template is skipped for such targets.
9. `obsidian vault=W open path=Spike/A.md`. Whether the CLI opens a note (search results now, the `open` kind later).
10. 20 warm `daily:append` calls timed: 95th percentile x 3, between 2 and 30 s, becomes `deadlines.write` (row 9).
11. `kill -STOP $(pgrep -x Obsidian)`, then `obsidian vault=W daily:read` with a 5 s timeout, then `kill -CONT`. A hang means `unknown` and the check are met often (row 3).
12. End to end: `config.toml` with the real `bin`, then `cmd plugin doctor plugins/vault --query "todo spike from cmd"` and `--run "capture:todo spike from cmd"`, with Obsidian running and then quit and reopened; the line lands once, and `vault` shows it waiting while Obsidian is closed.
<!-- SECTION:NOTES:END -->
