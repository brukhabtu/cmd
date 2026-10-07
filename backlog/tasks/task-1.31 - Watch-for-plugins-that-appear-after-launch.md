---
id: TASK-1.31
title: Watch for plugins that appear after launch
status: To Do
assignee: []
created_date: '2026-10-07 05:02'
updated_date: '2026-10-07 05:27'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
watch_plugins in crates/cmd-host/src/host.rs watches the plugin directories found at startup. A plugin copied into ~/Library/Application Support/cmd/plugins while the app runs is neither started nor watched until the app restarts. Watch the roots from manifest::plugin_dirs for new directories with a cmd-plugin.toml and start them; the indices in HostEvent must stay stable for the plugins already running. From the review of TASK-1.14.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin directory added to a plugin root while the app runs is started, the window says so, and its answers appear without a restart
- [ ] #2 Indices of the plugins already running do not change
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the review of 1.33: a reload that changes a plugin's manifest name to one already running is not checked against the others (start_again reads the manifest alone), so the duplicate rule belongs wherever plugins are added or renamed at runtime; cover it here with the new-plugin path.
<!-- SECTION:NOTES:END -->
