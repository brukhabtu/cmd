---
id: TASK-2
title: A launcher that runs an engineering manager's day
status: To Do
assignee:
  - '@brukhabtu'
created_date: '2026-10-08 13:46'
labels:
  - size-8
dependencies: []
type: intent
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
I manage a full-stack team. My day is people, context switches and decisions, not writing code, so what I need from a launcher is to reach the right thing or person fast and to capture a thought before it is gone. My notes and to-dos live in Obsidian. My tickets, reviews, calendar and on-call live in systems I already have my own clients for. The launcher has no way yet to write to Obsidian, to hold state, or to take a provider I write, and the plugin contract has gaps that would make those plugins fragile.

## Open questions
- [ ] Does the vault plugin use the obsidian CLI alone, or the CLI plus direct file writes when Obsidian is closed? Leaning: the CLI with an outbox; settled by the CLI spike.
- [ ] Which calendar source does the calendar provider read?
- [ ] Which provider interfaces come first: tickets, reviews, calendar, on-call, incidents?
- [x] Do background-task indicators ship in this intent? No. They are deferred to a draft; failures persist until dismissed when they are built.
- [x] Is the Obsidian vault plugin configurable? Yes: paths, templates and the to-do line format come from a config file; Obsidian core templates are referenced by name.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 From the launcher, typing todo <text> adds a task to today's daily note through the obsidian CLI, and a capture made while Obsidian is closed is not lost
- [ ] #2 Typing 1:1 <person> creates or opens that person's note from an existing Obsidian core template
- [ ] #3 Paths, template names and the to-do line format come from a config file; no vault-specific value is in the code
- [ ] #4 Typing never launches Obsidian and no call to the obsidian CLI in a query outlasts the host's query timeout
- [ ] #5 An integration is a provider command behind an interface the SDK defines; no vendor client and no credential is in the repository
- [ ] #6 The split between kernel, SDK and plugins, and the contracts between them, are written in one decision that docs/architecture.md agrees with
- [ ] #7 Plugins written for protocol 0 and 1 still load, and scripts/check.sh passes
<!-- AC:END -->
