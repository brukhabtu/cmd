---
id: DRAFT-2
title: 'Skill: changing the plugin protocol'
status: Draft
assignee:
  - '@brukhabtu'
created_date: '2026-10-07 02:41'
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
