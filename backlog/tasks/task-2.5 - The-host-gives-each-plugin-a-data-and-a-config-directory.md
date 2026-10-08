---
id: TASK-2.5
title: The host gives each plugin a data and a config directory
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-2
dependencies:
  - TASK-2.1
modified_files:
  - crates/cmd-host/src/host.rs
  - crates/cmd-host/src/process.rs
  - docs/plugin-protocol.md
parent_task_id: TASK-2
type: task
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A plugin that writes next to itself restarts itself, because the watched directory is its working directory. The host sets CMD_PLUGIN_DATA and CMD_PLUGIN_CONFIG to per-plugin directories under Application Support, creates the data one, and leaves both out of the watch. The config path is where the user's TOML for that plugin lives; a change to it restarts the plugin.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin writing a file in its data directory is not restarted
- [ ] #2 Both paths reach the plugin as environment variables and are in docs/plugin-protocol.md
- [ ] #3 A change to the plugin's config file restarts it and the window says reloaded
<!-- AC:END -->
