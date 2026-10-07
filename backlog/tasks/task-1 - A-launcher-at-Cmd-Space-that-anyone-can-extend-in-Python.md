---
id: TASK-1
title: A launcher at Cmd-Space that anyone can extend in Python
status: To Do
assignee:
  - '@brukhabtu'
created_date: '2026-10-07 02:40'
labels:
  - size-8
dependencies: []
type: intent
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
Spotlight is the fastest way to reach anything on a Mac and it is not extensible. Raycast is extensible and is a closed product with a TypeScript-only extension model. I want the launcher I reach for at Cmd-Space to be mine: a small Rust core with a GPUI window, and plugins in Python so that anyone who can write a script can add a command, a search, or a shortcut without touching the Rust.

## Open questions
- [ ] Does the launcher replace Spotlight's hotkey, or sit beside it on another one?
- [ ] Is the first distribution a plain binary for people who have uv, or a bundle that carries Python?
- [ ] Which three plugins would make it the daily driver on day one?
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Pressing the hotkey anywhere on the Mac shows the launcher within 100 ms with an empty, focused input
- [ ] #2 Typing shows results from every installed plugin that wants the query, merged into one list, without the typing ever blocking on a plugin
- [ ] #3 Enter performs the chosen item's action and the window hides
- [ ] #4 A plugin is a directory with a manifest and a Python file; the SDK and the protocol document are enough to write one without reading the Rust
- [ ] #5 A crashing or hanging plugin is reported in the window and never takes the launcher down
- [ ] #6 Everything in the repository is checked by one script that CI runs
<!-- AC:END -->
