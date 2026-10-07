---
id: TASK-1.34
title: 'cmd plugin install, update, remove and list on the app binary'
status: In Progress
assignee: []
created_date: '2026-10-07 05:24'
updated_date: '2026-10-07 07:28'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. A subprocess wrapper for the version-control tool (terminal prompts off) and an index module (parse, fetch from the remote's default branch) in cmd-host, with unit tests. 2. install.rs pure part: Source::classify, Record, rewrite_sdk_source, install_root, plain_name, unit tests. 3. doctor.rs moved from the cmd-doctor binary; cli.rs dispatching install/update/remove/list/doctor; a cmd-plugin bin; tests/doctor.rs re-pointed. 4. install (index, URL, path), remove, list, update with functional tests against local repositories in tests/plugin_cli.rs. 5. The dispatch at the top of cmd-app main(), scratch-workspace clippy. 6. Tutorial, README and architecture.md; scripts/check.sh.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From 1.35: the plugins listed from inside this repository depend on cmd-sdk as a workspace member (cmd-sdk = { workspace = true }), which cannot resolve once the plugin is installed on its own. The install must rewrite that one source to the git source at the same ref (git = <source>, subdirectory = python/cmd-sdk, rev = <commit>), and say so in .cmd-install.toml.

Landed: cmd-host gains cli.rs (cmd plugin install/update/remove/list/doctor; usage mistakes exit 2, failures 1), install.rs (Source::classify, the .cmd-install.toml Record, the SDK-source rewrite from the workspace form to the source repository at the installed commit, staging under a hidden directory with a rename into place, and install, update, remove, list), index.rs (parse, and a one-fetch read of plugins/index.toml from the tip of CMD_INDEX or this repository), git.rs (the person's own git as a subprocess with prompts off, a missing HTTPS repository reworded), doctor.rs (the cmd-doctor body moved; its usage line now reads cmd plugin doctor) and the cmd-plugin binary. cmd-doctor is gone and tests/doctor.rs drives cmd-plugin doctor. cmd-app's main gains only the dispatch at its top and returns ExitCode. Tutorial steps 4 and 5, README.md and docs/architecture.md say so.

Evidence: scripts/check.sh all checks passed (exit 0). cargo test --workspace --exclude cmd-app green: 30 cmd-host unit tests and 10 functional tests in tests/plugin_cli.rs against local repositories, with the real calculator installed from this checkout answering 6 * 7 through uv on the rewritten SDK source; URL install with the one-time warning; an owner/name that does not exist; a path copy without .venv; an index update to a moved ref with the rewrite moved, and a changed source or a delisted entry refused with the tree byte-identical; a cloned update fast-forwarded, an edited and a diverged clone refused in git's own words; update of everything exits 1 if any failed; remove with and without a record; list with every origin and the unreachable-index line at exit 0; every fetching command with git absent says how to get it. Mutation: with the SDK rewrite disabled, 2 of the 10 functional tests fail. Scratch-workspace cargo clippy -p cmd-app --all-targets -D warnings: exit 0.

Owed on a Mac: run cmd plugin list from the real cmd binary and see no window and no hotkey; an install lands in ~/Library/Application Support/cmd/plugins and the app finds it on the next launch; cmd plugin install calculator against GitHub, once the index's pinned commits are reachable from a lasting branch; a running app picking up an index update after the directory swap (FSEvents is path-based, inotify is not); a newcomer following the revised tutorial.

Notes: the warning before the first install from outside the index is printed, not confirmed, as decision 8 words it. A cloned plugin whose pyproject was rewritten keeps the SDK pinned at its install commit after a fast-forward: the line is no longer the workspace form and that commit still exists; only a plugin that is itself a uv workspace with cmd-sdk as a member is affected. The pinned index commits exist on this branch only until it is merged; the tests never touch GitHub. For 1.31: the new-plugin watcher must skip dot-directories, since the staging and the retired copy live in the root as .staging-<pid> and .old-<name>-<pid> for the life of a command. Awaiting review.
<!-- SECTION:NOTES:END -->
