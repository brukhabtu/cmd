---
id: TASK-1.33
title: The host refuses the second plugin of a name
status: To Do
assignee: []
created_date: '2026-10-07 05:23'
labels:
  - size-1
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two plugin directories can declare the same manifest name, for instance an installed copy under the per-user directory and a stale one in ./plugins or CMD_PLUGINS, and today both load and both answer. Load the first in the order of the plugin directories and report the second as a start failure naming both directories, so nothing is silently shadowed. From decision 8.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With two directories declaring one name, the first in plugin_dirs order loads and the second is a StartError naming both directories, shown in the window as 1.30 shows start failures
<!-- AC:END -->
