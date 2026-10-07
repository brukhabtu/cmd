---
id: TASK-1.13
title: Plugin install locations and discovery
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:24'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 14000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Plugins load from ~/Library/Application Support/cmd/plugins, and from CMD_PLUGINS when set
- [ ] #2 A directory with a bad manifest is reported with its path and the parse error; the others still load
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. cmd-host manifest: a pure plugin_dirs(env, home, cwd) that lists where to look (CMD_PLUGINS entries when set; otherwise the per-user directory and ./plugins when present), and discover_all over several roots that skips a missing root and reports a bad manifest with its path.
2. Tests on a temporary directory with one good and one bad plugin.
3. cmd-app uses them; README names the locations.
### Risks
The macOS path is built from HOME; no dirs crate.
### Proof
cargo test -p cmd-host; scripts/check.sh.
<!-- SECTION:PLAN:END -->
