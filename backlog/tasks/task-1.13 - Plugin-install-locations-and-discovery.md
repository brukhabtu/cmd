---
id: TASK-1.13
title: Plugin install locations and discovery
status: Done
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:34'
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
- [x] #1 Plugins load from ~/Library/Application Support/cmd/plugins, and from CMD_PLUGINS when set
- [x] #2 A directory with a bad manifest is reported with its path and the parse error; the others still load
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented in 668dee8: manifest::plugin_dirs (CMD_PLUGINS list, else the per-user directory and ./plugins when present), manifest::discover_all (skips a missing root, reports a bad manifest with its path beside the plugins that loaded), the app uses both, README names the locations. Unit tests on a scratch directory. Awaiting review.

Closed by the close-out reviewer on the second pass. Its notes: CMD_PLUGINS replaces the user directory rather than adding to it (documented); the stale line in docs/plugin-protocol.md is fixed in the same commit; a TOML syntax error takes the same LoadError path as the tested semantic error but is untested.
<!-- SECTION:NOTES:END -->
