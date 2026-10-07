---
id: TASK-1.41
title: 'Inside the bundle, plugins run on the bundle''s uv and a uv-managed Python'
status: In Progress
assignee: []
created_date: '2026-10-07 11:04'
updated_date: '2026-10-07 11:26'
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
- [x] #1 When the executable's canonical path is under Contents/MacOS, plugins start with PATH led by that directory, UV_PYTHON_INSTALL_DIR and UV_CACHE_DIR under ~/Library/Application Support/cmd and UV_PYTHON_PREFERENCE=only-managed; outside a bundle nothing is set; proven by a functional test through the real process with a fake plugin that echoes its environment
- [x] #2 Before the first plugin starts, uv python install 3.15 --no-bin runs with that environment and a failure is shown as start trouble; proven with a fake uv script that records its arguments
- [x] #3 cmd plugin doctor is unchanged
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
cmd-host: bundle.rs (Bundle::detect, environment, install_python, start_reporting that fetches Python then starts the host), PluginProcess::spawn_in, Host::start_in/start_reporting_in with the env kept on the Worker for restarts, two Startup variants for the fetch. cmd-app: the cmd-startup thread canonicalises current_exe, detects the bundle and goes through bundle::start_reporting; the starting line says Python is being fetched and a failed fetch joins the start trouble. Functional tests with a fake plugin echoing its environment and a fake uv recording its arguments.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed. cmd-host: bundle.rs (Bundle::detect from the canonical exe and HOME, Bundle::environment, python_install_command, install_python returning uv's stderr on failure, and bundle::start_reporting, which outside a bundle is Host::start_reporting and inside one reports FetchingPython, runs the fetch, reports FetchedPython(result), then starts the host with the environment); PluginProcess::spawn_in and Host::start_in / start_reporting_in, with spawn, start and start_reporting delegating with an empty environment, so no existing caller or test changed; the Worker keeps the environment, so a restart or a reload runs on the same uv. Startup gained FetchingPython and FetchedPython(Result<(), String>): the plan suggested reusing the Starting report or the note_trouble channel, and a Startup report does that without a channel of its own. cmd-app main.rs, start-up path only: the cmd-startup thread canonicalises current_exe, detects the bundle and goes through bundle::start_reporting; on_startup puts a sentinel first on the starting list while the fetch runs, so the line under the input reads 'fetching Python 3.15, then starting ...' without a new field on LauncherView (1.27 edits that struct), and a failed fetch joins the start trouble through note_trouble. cmd plugin doctor is untouched (AC 3). Docs: the 'Not yet' section of docs/architecture.md and decision 7's consequences say the wiring has landed.

Evidence: cargo test -p cmd-host: tests/bundle.rs 6 passed (a fake cmd.app under a temp dir; a fake plugin found only through the bundle's PATH echoes PATH, UV_PYTHON_INSTALL_DIR, UV_CACHE_DIR and UV_PYTHON_PREFERENCE, before and after a restart; outside a bundle they equal the test process's own; a fake uv records 'python install 3.15 --no-bin' and the environment, and runs before the plugin's Up report; a failing fake uv gives FetchedPython(Err) carrying its stderr and the plugin still starts; a bundle without uv says it could not run it); the bundle unit tests, 5 passed. Mutation: with the Worker's env dropped, the restart test fails. Scratch workspace: cargo clippy -p cmd-app --all-targets -D warnings clean, cargo test -p cmd-app 13 passed including the starting line. scripts/check.sh: all checks passed.

Owed on a Mac: launch cmd.app from the Dock with no ~/Library/Application Support/cmd/python and see 'fetching Python 3.15, then starting ...' under the input, then plugins answering; ~/Library/Application Support/cmd/python holds a CPython 3.15 and nothing was linked into ~/.local/bin; a second launch is quick; with the network off on a first launch the window shows uv's error as start trouble; launched through the cask's symlink, the bundle is still detected.
<!-- SECTION:NOTES:END -->
