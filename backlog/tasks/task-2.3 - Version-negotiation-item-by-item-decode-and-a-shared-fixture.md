---
id: TASK-2.3
title: 'Version negotiation, item-by-item decode and a shared fixture'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 20:41'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the review of TASK-2.1 (2026-10-08): decision 9 is proposed, and its assumptions need the owner's yes before this task builds the negotiation as written, above all the name of the list (capabilities) and the rule that the SDK errors on a kind the agreed version lacks.

From the worker (2026-10-08), branch worktree-agent-a57a3913f33d1da31, one commit with code, docs and this note. Built as decision 9 is written; its assumptions are still the owner's to confirm.

What was done:
- Negotiation. cmd-core: `Method::Describe` carries `capabilities` (missing means empty), `CAPABILITIES` is empty, `Method::describe()` sends `{"protocol": 1, "capabilities": []}`, `ACCEPTED` is `0..=VERSION`. The host and `cmd plugin doctor` send it. SDK: `Describe` reads the list; `agree()` gives `Agreement(min(host, PROTOCOL), capabilities)`; `serve` keeps it from the last describe; the describe answer carries the agreed version. `ICON_KIND_SINCE` and `EFFECT_KIND_SINCE` record when each kind arrived, and a kind newer than the agreed version is a `plugin_error` naming the kind and both versions. `Plugin(describe=...)`, optional, is called with the `Agreement` and its `Description` is sent: that is how a plugin reads both.
- Item-by-item decode. `Items` decodes each element on its own; a failure goes into `Items.dropped` as `item N ("id"): reason`. An icon that does not decode is none; a score is clamped to 0..1 when decoded. An unknown effect kind still fails the whole answer. The host's worker sends `HostEvent::Trouble` after the answer, "left out N item(s) it could not read: ..."; the window already shows Trouble as a note prefixed with the plugin's name, so no window code changed. The doctor prints the same note.
- Golden fixture `docs/plugin-protocol.golden.json`, checked by `crates/cmd-core/tests/golden.rs` and `python/cmd-sdk/tests/unit/test_golden.py`.
- `docs/plugin-protocol.md`: the false claim replaced, Negotiation and How the contract grows in place of Versions, item-by-item decode, clamping, unreadable icons, unknown effects, errors, Golden exchanges.
- Adapter test `crates/cmd-host/tests/calculator.rs`: a version 0 describe through the real calculator answers 0 and sends no icon; every real plugin agrees version 1 with this host.

Assumptions:
1. At version 0 the SDK leaves `icon` out rather than refusing the item: v0 has no icon field, decision 9 would call it an optional field, and leaving it out never sends a line a strict v0 host could reject. Kinds beyond the agreed version are refused, as decision 9 says. No kind is newer than 1 yet, so that refusal is tested by patching the tables.
2. Before any describe the SDK assumes its own version and no capabilities; a real host always describes first.
3. Any icon the host cannot read (unknown kind, known kind in the wrong shape, not an object) is no icon, not a lost item.
4. `capabilities` present but not a list of names, null included, is a `bad_request`; a negative `protocol` too.
5. The dropped-items note reuses `HostEvent::Trouble`, which carries no generation: a note about a stale query can show beside a newer query's rows until the next keystroke. A generation-tagged event would need window changes.
6. The SDK still sends a score outside 0..1 as it is (it checks only that it is finite); the host clamps. Whether the SDK should refuse one is open.
7. The fixture sits beside the spec in `docs/`, so the site publishes it for plugins in other languages.
8. `Plugin.describe` is a new optional field: making `description` itself a callable broke a plugin's type-checked tests.

Evidence: `scripts/check.sh` ends "all checks passed". Each change was undone once and its tests failed, then restored: no clamping (score unit test, golden), a strict icon (icon unit test, golden), no note from the host (host test times out), `agree()` returning the SDK's version (5 Python tests and the adapter test), the icon kept at version 0 (2 Python tests). cmd-app is not built on Linux; no window code changed.
<!-- SECTION:NOTES:END -->
