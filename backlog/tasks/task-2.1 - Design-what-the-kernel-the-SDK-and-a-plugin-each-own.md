---
id: TASK-2.1
title: 'Design: what the kernel, the SDK and a plugin each own'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 18:34'
labels:
  - size-3
dependencies: []
references:
  - >-
    backlog/decisions/decision-9 -
    What-the-kernel-the-SDK-and-a-plugin-each-own-and-how-the-contract-grows.md
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Decision 9 written (proposed): backlog/decisions/decision-9 - What-the-kernel-the-SDK-and-a-plugin-each-own-and-how-the-contract-grows.md.

Changed:
- Decision 9: who owns what (core, host, window, SDK, plugin); three kinds of change (optional field, capability, new version); negotiation (protocol and capabilities in describe, plugin answers the lower version); the obsidian CLI and provider rules; what the CLI spike must answer and what each answer changes; plugin-initiated messages and task indicators deferred, with reasons.
- Decision 6 amended, not superseded: v1 carries icon, details waits; title, Decision and Consequences changed, Context kept. File renamed to the new title (old path deleted).
- docs/architecture.md: the SDK named, a paragraph on the split and the growth rule, the host to core dependency spelled out, two component views.
- LikeC4: the host to core edge no longer says the host merges (the state machine does); the edge was already drawn. New plugin components SDK and Plugin code with a view; host to plugin and plugin to macOS edges moved onto them; host and core descriptions name protocol versions.

Assumed (in the decision, for the owner to confirm): the kernel includes cmd-app; data and config directories are environment, so need no version or capability, and the SDK raises without them; the list is named capabilities, missing means empty; blank input needs no capability, several keywords do; a kind the agreed version lacks is an SDK error, not a quiet fallback; amending decision 6 is enough.

Owed elsewhere: docs/plugin-protocol.md needs the three kinds of change in place of its Versions paragraph, the negotiation and the two variables (tasks 2.3 and 2.5). Draft 10's LikeC4 edge item is done here.
<!-- SECTION:NOTES:END -->
