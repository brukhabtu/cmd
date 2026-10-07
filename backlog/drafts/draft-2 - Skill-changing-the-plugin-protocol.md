---
id: DRAFT-2
title: 'Skill: changing the plugin protocol'
status: Draft
assignee:
  - '@brukhabtu'
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 05:13'
labels:
  - size-3
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Evidence
None yet. The protocol has three homes (crates/cmd-core/src/protocol.rs, python/cmd-sdk/src/cmd_sdk/protocol.py, docs/plugin-protocol.md) and one proof (the adapter test). The first time a change lands in one home and not the others, this draft has its evidence.

## Eval cases it must pass
1. "Add an optional icon field to Item" -> file_exists and regex graders on all three homes, and the adapter test still passes.
2. "Bump the protocol to v1 with a new method" -> regex for VERSION in both sides and the compatibility note in the document.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Review before milestone 2 (2026-10-07): task 1.28 changed the host's version acceptance and the document without touching the wire or the SDK, and the reviewer found every home consistent, so there is still no demonstrated miss. The first wire change is 1.24 (icons, protocol 1); if one of the three homes or the adapter test is missed there, that is this draft's first evidence. Stays a draft.
<!-- SECTION:NOTES:END -->
