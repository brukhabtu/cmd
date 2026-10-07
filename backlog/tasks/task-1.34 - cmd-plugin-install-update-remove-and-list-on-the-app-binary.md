---
id: TASK-1.34
title: 'cmd plugin install, update, remove and list on the app binary'
status: To Do
assignee: []
created_date: '2026-10-07 05:24'
updated_date: '2026-10-07 05:31'
labels:
  - size-3
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 8. The app binary reads its arguments before any window or hotkey exists. install takes a name from plugins/index.toml (fetched at the pinned commit, keeping the subdirectory when the entry has one), a git URL or owner/name (shallow clone of the default branch, after a one-time warning that this runs someone's code), or a local path (copied); refuses a source without cmd-plugin.toml, a manifest whose name is not the install directory, and an existing directory. It writes .cmd-install.toml (source kind, index name, URL, ref) into the plugin directory. update moves an index plugin to the index's current ref only and fast-forwards a URL plugin; a failed fast-forward or a changed source changes nothing and says so. remove deletes; list shows what is installed, from where and at what. Writes go to the per-user directory, or the first CMD_PLUGINS entry. cmd-doctor becomes cmd plugin doctor.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of install (index name, URL, owner/name, path), update, remove and list behaves as decision 8 says, with a functional test per source kind against a local git repository
- [ ] #2 cmd plugin ... never opens a window or registers the hotkey
- [ ] #3 cmd-doctor's behaviour is reachable as cmd plugin doctor <dir> and the tutorial says so
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From 1.35: the plugins listed from inside this repository depend on cmd-sdk as a workspace member (cmd-sdk = { workspace = true }), which cannot resolve once the plugin is installed on its own. The install must rewrite that one source to the git source at the same ref (git = <source>, subdirectory = python/cmd-sdk, rev = <commit>), and say so in .cmd-install.toml.
<!-- SECTION:NOTES:END -->
