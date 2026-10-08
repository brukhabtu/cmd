---
id: DRAFT-8
title: Feeds plugin and the provider contract
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-3
dependencies: []
parent_task_id: TASK-2
type: design
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
One plugin, configured with providers, not five. A provider is a user-supplied command: input {"contract":1,"op":"describe"|"list","args":{"kind":...}} on stdin, output {"contract":1,"records":[{id,kind,title,url,subtitle?,state?,updated?}]}, or a non-zero exit with {"error":{"code":"auth|unavailable|bad_args","message"}}. Kinds: tickets, reviews, calendar, oncall, incidents. The SDK holds the typed records and a doc; query reads only a cache a background thread refreshes; commands are absolute paths. A contract test runs a fake provider through the real adapter. No vendor client and no credential in this repository.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The contract and the first interfaces are written down with a contract test over a fake provider
- [ ] #2 query never waits on a provider, and a provider failure shows its message
<!-- AC:END -->
