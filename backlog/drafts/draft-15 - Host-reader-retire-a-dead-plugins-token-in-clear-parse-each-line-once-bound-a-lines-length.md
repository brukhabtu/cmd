---
id: DRAFT-15
title: >-
  Host reader: retire a dead plugin's token in clear(), parse each line once,
  bound a line's length
status: Draft
assignee: []
created_date: '2026-10-14 19:35'
labels:
  - size-2
dependencies: []
type: bug
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the TASK-7 review. (1) Between tasks.clear() on a restart and activate(new token), a line the dead process still had buffered carries the current token and can put a stale Task event on the channel before Restarted; retire the old token in clear(). (2) The reader parses every line to a serde_json::Value in classify and again as a response; parse once. (3) read_line is unbounded, so one huge line from a plugin is held whole; cap it (a line over the cap is NotProtocol and the plugin is treated as misbehaving). crates/cmd-host/src/{process,tasks}.rs.
<!-- SECTION:DESCRIPTION:END -->
