---
id: TASK-2.7
title: 'Design: the vault plugin''s config, captures and outbox'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies:
  - TASK-2.4
  - TASK-2.1
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
- [ ] #1 A decision records the config schema with one worked example per capture kind
- [ ] #2 The outbox's states and its retry and duplicate rules are written down
- [ ] #3 The query path never raises and never launches Obsidian, and says how a closed Obsidian is shown
<!-- AC:END -->
