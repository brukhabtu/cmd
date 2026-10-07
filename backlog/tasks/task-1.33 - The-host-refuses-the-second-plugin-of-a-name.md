---
id: TASK-1.33
title: The host refuses the second plugin of a name
status: Done
assignee: []
created_date: '2026-10-07 05:23'
updated_date: '2026-10-07 05:27'
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
- [x] #1 With two directories declaring one name, the first in plugin_dirs order loads and the second is a StartError naming both directories, shown in the window as 1.30 shows start failures
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Host::start keeps the first plugin of a name and pushes StartError::Duplicate for a later directory declaring the same manifest name, naming both directories; the window shows it through the start-trouble line (1.30).
2. Host test with two directories declaring 'a'; the protocol document's plugin-locations paragraph says so.
### Proof
cargo test -p cmd-host --test host; scripts/check.sh.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: Host::start keeps the first plugin of a manifest name and pushes StartError::Duplicate ('<name> is already running from <dir>; not starting the copy in <dir>') for a later directory with the same name, before any handshake, so the window shows it through the start-trouble line. Test a_second_directory_declaring_a_running_name_is_refused_naming_both. The protocol document's plugin-locations paragraph says so. Awaiting review.

Closed on the reviewer's verdict against 1159f73. Edges accepted, none blocking: when the first copy fails to start, a later copy of the name loads; names are compared from the manifest, not the description; a reload that renames a plugin to a running name is not checked (noted on 1.31).
<!-- SECTION:NOTES:END -->
