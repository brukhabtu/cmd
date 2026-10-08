---
id: TASK-2.5
title: The host gives each plugin a data and a config directory
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 20:31'
labels:
  - size-2
dependencies:
  - TASK-2.1
modified_files:
  - crates/cmd-host/src/host.rs
  - crates/cmd-host/src/process.rs
  - docs/plugin-protocol.md
parent_task_id: TASK-2
type: task
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A plugin that writes next to itself restarts itself, because the watched directory is its working directory. The host sets CMD_PLUGIN_DATA and CMD_PLUGIN_CONFIG to per-plugin directories under Application Support, creates the data one, and leaves both out of the watch. The config path is where the user's TOML for that plugin lives; a change to it restarts the plugin.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin writing a file in its data directory is not restarted
- [ ] #2 Both paths reach the plugin as environment variables and are in docs/plugin-protocol.md
- [ ] #3 A change to the plugin's config file restarts it and the window says reloaded
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built: Host::start_reporting_with(plugins, timeouts, env, user_dir, report) sets CMD_PLUGIN_DATA and CMD_PLUGIN_CONFIG on every plugin process (start and restart), creates plugin-data/<name>, never creates plugin-config/<name>. manifest.rs: user_cmd_dir(home) (user_plugin_dir is now its 'plugins' child), plugin_data_root, plugin_config_root, is_directory_name. bundle::start_reporting and the app pass user_dir from HOME. Test hook: the per-user directory is a parameter (as home is for plugin_dirs), so tests pass a scratch directory. Tests: crates/cmd-host/tests/plugin_dirs.rs. Control tests show the old behaviour (a write inside the watched plugin directory, or a data directory placed there, does reload).
Config watch: the host watches the plugin-config root recursively (creating that root if missing, not the plugin's directory) and routes events by plugin name. Chosen over polling or watching an ancestor: one watch, no timer, a directory that appears later is an event. 
Assumptions: user_dir None (Host::start, start_in, start_reporting) sets neither variable and watches nothing extra, so older tests never touch a home directory; only the app path passes it. A manifest name that cannot be one directory name (empty, ., .., separator) is a start failure. The data directory is created at first start only, not recreated on restart if deleted mid-run. The config path uses the manifest name read at start. Any non-hidden file in the config directory reloads, not only config.toml. If plugin-config root is deleted while running, the watch is lost until restart. cmd-app edit (main.rs) is not compiled on Linux.
<!-- SECTION:NOTES:END -->
