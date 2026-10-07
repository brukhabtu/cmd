---
id: TASK-1.28
title: The host accepts protocol 0 and 1
status: Done
assignee: []
created_date: '2026-10-07 04:44'
updated_date: '2026-10-07 05:11'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 6 promises compatibility across v0 and v1; the host currently refuses any version other than its own.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A plugin describing itself as protocol 0 or 1 is loaded; any other version is refused with the message naming both
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. cmd-core: ACCEPTED, the versions this host loads (0 to 1), beside VERSION, the one it speaks; a test that VERSION is accepted.
2. cmd-host: the handshake refuses only a version outside ACCEPTED, with a message naming the plugin's version and the accepted range; cmd-doctor the same.
3. Host test with fakes speaking 1 and 2: the first loads, the second is refused by name.
4. docs/plugin-protocol.md says what the host sends, what it accepts and why 1 is safe to accept (optional fields only).
### Risks
A v1 plugin's optional fields are ignored by this host until 1.24 reads them; the document says so.
### Proof
cargo test -p cmd-host --test host; scripts/check.sh.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: cmd_core::protocol::ACCEPTED (0 to 1) beside VERSION (0, what the host sends); the handshake in cmd-host and cmd-doctor refuse only a version outside it, with '<name> speaks protocol N, this host accepts 0 to 1'. Test a_plugin_speaking_the_next_protocol_loads_and_an_unknown_one_is_refused_by_name starts fakes speaking 1 and 2: the first loads and answers, the second is the one error, by name. Unit test that VERSION is accepted. docs/plugin-protocol.md's Description section says what the host sends, what it loads and why 1 is safe (optional fields only). Nothing on the Python side changed: the SDK still answers with the version it speaks. Awaiting review.

Closed on the reviewer's verdict against 9269e7e. From the review: Effect is tagged by kind, so an unknown kind fails to decode; a new effect kind therefore needs a new protocol version, never an optional field. Written into the protocol document and decision 6.
<!-- SECTION:NOTES:END -->
