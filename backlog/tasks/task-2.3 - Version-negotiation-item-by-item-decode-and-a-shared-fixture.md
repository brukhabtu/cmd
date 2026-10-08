---
id: TASK-2.3
title: 'Version negotiation, item-by-item decode and a shared fixture'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies:
  - TASK-2.1
modified_files:
  - crates/cmd-core/src/protocol.rs
  - python/cmd-sdk/src/cmd_sdk/protocol.py
  - docs/plugin-protocol.md
parent_task_id: TASK-2
type: task
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The host announces its protocol version and what it supports in `describe`; the SDK answers with min(host, its own) and holds back kinds an older host cannot decode. The host decodes items one by one, treats an unknown icon kind as no icon, and clamps scores to 0..1. One golden fixture is decoded by both Rust and Python. docs/plugin-protocol.md is corrected where it claims a version 1 plugin runs under a version 0 host.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin answers with min(host version, its own) and an old host is never sent a kind it cannot decode
- [ ] #2 One bad item or an unknown icon kind loses that item or icon only, and an out-of-range score cannot outrank 1.0
- [ ] #3 A golden fixture is decoded by both sides in tests
- [ ] #4 docs/plugin-protocol.md, protocol.rs and protocol.py change in one commit and the adapter test passes
<!-- AC:END -->
