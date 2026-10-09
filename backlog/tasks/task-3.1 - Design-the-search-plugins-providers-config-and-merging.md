---
id: TASK-3.1
title: 'Design: the search plugin''s providers, config and merging'
status: To Do
assignee: []
created_date: '2026-10-09 13:51'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-3
type: design
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Settle before any code, since a config format is hard to change once people write it. One plugin, `search`, configured with providers. Decide, in one decision (the next number is 11), using the qmd findings on TASK-3:
- The provider interface in code (what a provider kind is given and returns, so a new kind is a small module) and the generic `command` kind (a user-supplied command and how its output is read), including how a provider's hits are ranked when its own scores cannot be trusted.
- The config TOML: providers, their keywords (providers may share one), the binary as an absolute path, the PATH handed to the process, collections, limits and deadlines, with a worked example for qmd and for a second provider. What the plugin shows for a missing or invalid config.
- How providers that share a keyword are searched together: parallel under one deadline shorter than the host's, merged and ranked, duplicates (the same file from two providers) collapsed, the provider named in each row, and what a failing or slow provider shows without hiding the others.
- How the plugin matches its own keywords until the protocol has several (decision 10 does the same for the vault), and the as-you-type cost: a word that is no keyword costs nothing, and what keeps a process from being started on every keystroke.
- What Enter and the other actions do with a hit: open the note, copy its path, anything the effects allow; and what a hit with no resolvable path does.
- Whether qmd's slow modes (query, vsearch) can ever be on the query path, and what would have to be true for them to be.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One decision records the provider interface, the config schema with a worked example for qmd and for a second provider, and how providers that share a keyword are merged
- [ ] #2 The decision says what a failing, slow or missing provider shows, and that query never raises and stays inside the host's timeout
- [ ] #3 The decision says how Enter, the other actions and a hit without a path behave
<!-- AC:END -->
