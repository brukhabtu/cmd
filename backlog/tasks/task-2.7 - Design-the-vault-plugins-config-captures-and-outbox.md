---
id: TASK-2.7
title: 'Design: the vault plugin''s config, captures and outbox'
status: Done
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 20:39'
labels:
  - size-3
dependencies:
  - TASK-2.4
  - TASK-2.1
references:
  - >-
    backlog/decisions/decision-10 -
    The-vault-plugins-config-outbox-and-query-path.md
parent_task_id: TASK-2
type: design
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Settle before any code, since a config format is hard to change once people write them: the TOML for captures (keyword, target path, core template by name, heading to insert under, to-do line format), views (search, open tasks), and the outbox (what is queued, when it is retried, how a duplicate is avoided when `run` times out). How the plugin matches its own keywords until the protocol has several, and what it returns for a first word that is not one of them. Absolute paths for the obsidian binary, because a Dock launch has a bare PATH.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A decision records the config schema with one worked example per capture kind
- [x] #2 The outbox's states and its retry and duplicate rules are written down
- [x] #3 The query path never raises and never launches Obsidian, and says how a closed Obsidian is shown
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Wrote decision 10 (backlog/decisions/decision-10 - The-vault-plugins-config-outbox-and-query-path.md), proposed: the config.toml schema with defaults and errors as rows, one worked example per capture kind (todo, note, 1:1), keyword matching until draft 5, the query path, and the outbox's states, retries and duplicate rule. Both TOML examples and the outbox entry's JSON parse (tomllib, json); scripts/docs.sh passes.
Task 2.4 has not run (it needs the owner's Mac). Nothing it will find is guessed: every place an answer changes a number or a branch is marked [2.4] in the decision and gathered in its table 'Where task 2.4 changes this'. The schema and the outbox are the same either way.
Assumptions, each also in the decision:
- Every keyword comes from config; todo, note and 1:1 are the examples.
- note appends a timestamped line to one inbox note; a note per capture is an open capture with a path such as Inbox/{date} {text}.md, not a new kind.
- 1:1 opens the note only within 60 s of Enter (a guess at a cold start, not a measurement). With Obsidian closed, Enter on 1:1 starts Obsidian (run may, query may not); Enter on todo or note queues and closes.
- Outbox rows appear only on the plugin's own keywords, and in full on the status keyword (vault by default).
- The SDK's config() returns the parsed config.toml and raises the parser's error with line and column, and a distinct error for a missing file.
- Retry numbers (5 s, 30 s, 2 min, 10 min; failed on the fifth failed call) live in code, not config.
- No direct file writes: the CLI alone, with the outbox. This answers task 2's CLI-versus-files question, for the owner to tick.
Owed elsewhere, not edited here: task 2.4 should also answer five things (heading insertion, which command reads a note and today's daily note, where the CLI is installed, what create does to an existing path, how a call names a vault); task 2.6's call must tell a killed call from a non-zero exit; draft 5 must let query say which keyword was typed; the open kind (1:1) and the tasks view need a task of their own after 2.8.
Review at close, 2026-10-08: a read-only reviewer who did not do the work said not yet, for two things, fixed in decision 10 (the lead's edit): config() returns {} for a missing file and raises ConfigError otherwise, not a distinct error for a missing one; and an unknown entry had no path to failed. Also fixed: the state is written to disk before each CLI call, the SDK call's kill_on_timeout and its OSError are named, the deadlines add up under the host's 3 s once the call's 1 s drain grace is counted (query now defaults to 1.5 s), and three guesses about the CLI are marked for the spike. Left for the owner: TASK-2.7 lists TASK-2.4 as a dependency and 2.4 has not run (it needs the Mac); closing 2.7 without it is the owner's call, and decision 10 says where each spike answer would change it.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Decision 10 (proposed) records the vault plugin's config schema with a worked example per capture kind, the outbox's states, retries and duplicate rule, and the query path (never raises, never launches Obsidian, a closed Obsidian shown as a row). Closed on review, with the fixes made. TASK-2.4, a listed dependency, has not run: it needs the owner's Mac, so every spike-dependent choice is marked [2.4] in the decision.
<!-- SECTION:FINAL_SUMMARY:END -->
