---
id: TASK-1.32
title: Start the host off the main path so the window opens before the first describe
status: In Progress
assignee: []
created_date: '2026-10-07 05:20'
updated_date: '2026-10-07 11:09'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
main() in crates/cmd-app/src/main.rs runs start_host before Application::new, and Host::start blocks on each plugin's describe for up to 60 s, so on a first launch the window does not exist until every handshake, including uv's one-time Python download under decision 7, has finished. Open the window first and start the host on a background task, reporting each plugin as it comes up, so the window can say what it is waiting on. From the review of task 1.22.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The window is on screen before any plugin has described itself, and says which plugins are still starting
- [ ] #2 A plugin whose first start fails is reported in the window as 1.30 does, not only on stderr
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. cmd-host: Startup reports and Host::start_reporting, with Host::start as a wrapper; StartError::name; re-export.
2. Tests: start_reports_each_plugin_in_order_with_its_index and a_plugin_is_reported_before_the_next_handshake_finishes through real fake plugins.
3. cmd-app: discovery on the main thread, window opened first, host started on a cmd-startup thread after open_window returns, reports fed to the view (starting line, failures through the 1.30 trouble line), Host handed over last.
4. Docs: architecture.md and plugin-protocol.md lifecycle sentence (no wire change).
5. scripts/check.sh green, scratch-workspace clippy for cmd-app under the shared lock, commit.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed (builder, not the reviewer):
- cmd-host: Host::start_reporting(plugins, timeouts, report) reports Startup::Up { plugin, name } or Startup::Failed(StartError) per plugin, in order, each before the next handshake; Host::start is now a wrapper that collects the failures, so its callers (cmd-doctor, the adapter test, every host test) are unchanged. StartError::name() gives the manifest name every variant carries. Startup is re-exported.
- Departures from the plan, because the code needed them: Startup::Up carries the manifest name, not the described name, so the window's starting list (built from manifests) can always strike it off, as StartError::name does; a Spawn error for a worker thread now names the plugin rather than its thread (it said plugin:<name> before). bring_up_host awaits relay_host_events itself once the host arrives instead of spawning a second task. The host test for early reports asserts that b's report comes at least 300 ms after a's (b's describe sleeps 300 ms) rather than bounding a's own time under 250 ms, which would only measure how busy the test machine is.
- cmd-app main.rs (only main, LauncherView::new and its struct, perform, waiting_on, plugin_name, plus new items): discovery (locate_plugins) stays on the main thread; the window opens with the manifest names; only after open_window returns is the cmd-startup thread spawned (start_host_beside), so the window exists before the first handshake by construction (AC #1). waiting_on says "starting a, b" until each is reported. A Startup::Failed goes through note_trouble into the 1.30 start-trouble line, shown at once and on every show until a key is pressed (AC #2), and to stderr. The host arrives last as Starting::Ready; text typed during start-up is then asked at the same generation, so nobody retypes. Enter during start-up does nothing (no hits), by design, not a bug.
- Docs: one sentence each in docs/architecture.md and the Lifecycle section of docs/plugin-protocol.md. No wire change: protocol.rs, protocol.py and the adapter test are untouched.

Evidence (Linux): cargo test -p cmd-host --test host: 18 passed, including start_reports_each_plugin_in_order_with_its_index, a_plugin_is_reported_before_the_next_handshake_finishes and a_plugin_that_cannot_be_spawned_is_named_by_its_manifest (none compiles without the change). cargo clippy --workspace --exclude cmd-app --all-targets -D warnings: clean. Scratch-workspace cargo clippy -p cmd-app --all-targets -D warnings: clean (proves Host: Send for the Linux watcher). scripts/check.sh: all checks passed.

Owed on a Mac (can share 1.30's sitting): launch with a cold plugin environment (delete plugins/*/.venv or point CMD_PLUGINS at copies outside the workspace, clear the uv cache) and see the window at once with "starting calculator, websearch" under the input, names dropping off as each comes up; type 2+2 while that line shows and see 4 once the calculator is up, without retyping; add a directory whose command is not on PATH and see its line at once, still there on the first chord press after a focus loss. CI's macOS build proves Host: Send with FsEventWatcher.
Follow-up not filed here: handshakes are still serial, so on a cold launch plugins come up one after another.
<!-- SECTION:NOTES:END -->
