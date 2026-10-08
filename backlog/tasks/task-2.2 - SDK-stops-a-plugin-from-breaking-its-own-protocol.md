---
id: TASK-2.2
title: SDK stops a plugin from breaking its own protocol
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-2
dependencies: []
modified_files:
  - python/cmd-sdk/src/cmd_sdk/serve.py
  - python/cmd-sdk/src/cmd_sdk/protocol.py
parent_task_id: TASK-2
type: task
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the contract review: a stray print, a PathIcon, a NaN score and an unknown method each break a call or the next one.

- `serve` keeps the real stdout for the protocol and points sys.stdout at stderr.
- The encoder checks types and finiteness, serialises inside the guarded block with allow_nan=False, and a bad item becomes a plugin_error naming it, not a dead process.
- An unknown method is answered with the request id and a new `unknown_method` code, never id 0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin that prints, returns a Path icon, a NaN or infinite score, or is sent an unknown method keeps serving, and the host gets an answer with the right id
- [ ] #2 Each case has an SDK test and the adapter test still passes
<!-- AC:END -->
