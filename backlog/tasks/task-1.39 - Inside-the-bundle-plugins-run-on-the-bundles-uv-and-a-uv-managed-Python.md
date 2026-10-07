---
id: TASK-1.39
title: 'Inside the bundle, plugins run on the bundle''s uv and a uv-managed Python'
status: To Do
assignee: []
created_date: '2026-10-07 11:04'
labels:
  - size-3
milestone: m-3
dependencies:
  - TASK-1.23
  - TASK-1.32
parent_task_id: TASK-1
type: task
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 7's runtime wiring, split from 1.23 (which builds cmd.app with uv in Contents/MacOS but does not use it). Without this a bundled cmd resolves uv from launchd's PATH and fetches no Python. Design from the 1.23 plan: crates/cmd-host/src/bundle.rs with a pure Bundle::detect(exe, home) -> Option<Bundle> and Bundle::environment(inherited_path) -> Vec<(OsString, OsString)>; PluginProcess::spawn_in(command, cwd, env) and Host::start_in(plugins, timeouts, env) delegating from the existing functions so no caller or test changes; the Worker keeps the env for start_again; start_host in main.rs canonicalises current_exe() before detection (the cask's symlink would otherwise hide the bundle). The install belongs on 1.32's window-first path so the window can say it is fetching Python.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When the executable's canonical path is under Contents/MacOS, plugins start with PATH led by that directory, UV_PYTHON_INSTALL_DIR and UV_CACHE_DIR under ~/Library/Application Support/cmd and UV_PYTHON_PREFERENCE=only-managed; outside a bundle nothing is set; proven by a functional test through the real process with a fake plugin that echoes its environment
- [ ] #2 Before the first plugin starts, uv python install 3.15 --no-bin runs with that environment and a failure is shown as start trouble; proven with a fake uv script that records its arguments
- [ ] #3 cmd plugin doctor is unchanged
<!-- AC:END -->
