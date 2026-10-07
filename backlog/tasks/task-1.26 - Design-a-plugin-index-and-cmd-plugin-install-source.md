---
id: TASK-1.26
title: 'Design: a plugin index and cmd plugin install <source>'
status: In Progress
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 05:23'
labels:
  - size-3
milestone: m-4
dependencies: []
parent_task_id: TASK-1
type: design
ordinal: 27000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision picks how plugins are found (a git-backed index, PyPI classifiers, or both) and how they are installed and updated
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Decision 8: how a plugin is found (a git-backed index in this repository, PyPI with a classifier or keyword, or both), how 'cmd plugin install <source>' puts it in the user plugin directory, and how it is updated; the sources it accepts (a git URL, a GitHub owner/name, a local path, a name from the index).
2. Consequences name the tasks that follow (the cmd CLI, the index file, the install locations already in 1.13) and what the SDK tutorial changes.
### Proof
The reviewer checks the reasoning against the tutorial's install step and decision 7.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Decision 8 written: a git-backed index (plugins/index.toml: name, summary, source, optional ref; listing is a pull request), 'cmd plugin install <name | git URL | owner/name | path>' cloning into the plugin directory, 'cmd plugin update' fast-forwarding, remove and list; the app's own binary takes the subcommands. PyPI is weighed and deferred to a later decision with evidence, since PyPI offers no keyword search and would make a ten-minute plugin need a release. The intent's open question on distribution is ticked with decision 7. Awaiting review.

Reviewer (working tree): KEEP OPEN, an optional ref let unreviewed code through the index. Decision 8 now requires ref (tag or commit) on every entry, installs and updates index plugins at that ref only (a shallow fetch of the commit, since clone --branch takes only tags and branches), adds an optional subdirectory so this repository's own plugins can be listed, names the install directory (per-user, or the first CMD_PLUGINS entry), says a failed fast-forward or a changed source changes nothing, has the host refuse the second plugin of a name (TASK-1.33), parses subcommands before any window or hotkey exists, folds cmd-doctor into 'cmd plugin doctor' later, and notes that an update reloads through 1.14 while a new install waits on 1.31. Awaiting review.
<!-- SECTION:NOTES:END -->
