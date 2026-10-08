---
id: TASK-2.1
title: 'Design: what the kernel, the SDK and a plugin each own'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies: []
parent_task_id: TASK-2
type: design
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Write one decision for the split, from the architecture review of 2026-10-08.

## Settle
- What is kernel (host or core), what is SDK, what is a plugin, by the test: the kernel owns what must see all plugins, needs OS privilege, or must look the same everywhere.
- Optional `describe` fields that need no version bump: several keywords, a home query for blank input, the plugin data and config directory. Which need a capability the host announces, and which new effects (paste, set-input) force a protocol bump.
- Capability negotiation: the host announces what it supports, the plugin answers with min(host, own).
- How the vault plugin reaches Obsidian (the obsidian CLI, never in the query path without its own deadline, an outbox for writes) and how a provider plugs in (a command, one shot, fed from a cache).
- Plugin-initiated messages and background-task indicators: deferred, with the reason.
- Amend decision 6, which promises a `details` field the code does not have.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One decision records the split, the optional-field versus bump rule, capability negotiation, the CLI and provider rules, and what is deferred
- [ ] #2 Decision 6 is amended or superseded to match the code
- [ ] #3 docs/architecture.md and the LikeC4 model agree with the decision, including the host to core edge
<!-- AC:END -->
