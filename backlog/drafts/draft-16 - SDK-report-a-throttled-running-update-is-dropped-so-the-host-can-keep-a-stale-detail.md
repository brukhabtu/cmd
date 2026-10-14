---
id: DRAFT-16
title: >-
  SDK report(): a throttled running update is dropped, so the host can keep a
  stale detail
status: Draft
assignee: []
created_date: '2026-10-14 19:48'
labels:
  - size-2
dependencies: []
type: bug
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the TASK-9 review. report() drops a running update inside the 0.5 s throttle window; the vault's Tracker records it as sent, so if nothing changes afterwards the host keeps the older detail (e.g. a line instead of 'waiting for Obsidian'). Fix in the SDK: hold back the newest withheld update and send it when the window passes (a timer thread or the next call), so the last state is always delivered; or have report() say whether it sent. Failed and done are already always sent. python/cmd-sdk/src/cmd_sdk/{reporter,tasks}.py.
<!-- SECTION:DESCRIPTION:END -->
