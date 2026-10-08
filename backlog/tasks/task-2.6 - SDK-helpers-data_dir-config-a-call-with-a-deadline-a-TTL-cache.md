---
id: TASK-2.6
title: 'SDK helpers: data_dir, config, a call with a deadline, a TTL cache'
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 20:32'
labels:
  - size-2
dependencies:
  - TASK-2.5
modified_files:
  - python/cmd-sdk/src/cmd_sdk/__init__.py
parent_task_id: TASK-2
type: task
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Files and system each wrote their own subprocess call with a deadline. Move it to the SDK, with the other helpers every plugin in this intent needs: `data_dir()`, `config()` (TOML from the config path), a subprocess call that keeps partial output and leaves a slow child to finish, and a TTL cache with a background refresh thread. Files and system then use the shared call.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The helpers exist with tests, and files and system use the shared call
- [ ] #2 The SDK still imports no plugin and scripts/import_boundaries.py passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From TASK-2.2 (2026-10-08): serve points sys.stdout at stderr, which stops a stray print. A child process the plugin starts still inherits file descriptor 1, the protocol's real stdout, unless it is given somewhere else; the obsidian CLI and any other tool a plugin runs without capturing its output would write into the protocol. The shared call this task builds should always capture or redirect the child's stdout (and keep it, since it keeps partial output anyway), and say so in its docstring.

TASK-2.6 work (2026-10-08). Built in cmd_sdk: data_dir() -> Path, config() -> dict (locate.py pure, environment.py shell), call(command, timeout) -> CallResult(returncode, stdout, stderr, timed_out) (calls.py), TtlCache(produce, ttl, *, block_first=False, clock=time.monotonic) with get(), error, wait() (expiry.py pure, cache.py shell). pypeeker allow-table extended in pyproject.toml. Files and system now use call(). Assumptions: (1) CMD_PLUGIN_DATA/CONFIG empty or whitespace counts as missing; the data directory is not checked for existence (the host creates it). (2) A config path that is a file, not a directory, gives {} like a missing one; non-UTF-8 text is a ConfigError. (3) call() returns bytes; plugins decode. Files and system differed: files killed a slow mdfind (subprocess.run), left stdin inherited, and system left the child running in its own session with stdin closed. The shared call follows the task text and system: the child is left to finish, in its own session, stdin closed (the safer: a child cannot read the protocol's requests). So a slow mdfind is no longer killed; it finishes in the background. If that piles up processes, add a kill option. (4) Process-start failure (OSError) is raised, not folded into the result; system catches it as before. (5) TtlCache.get() returns None before the first fill; a failed refresh, first or later, stamps the attempt so the next try waits one ttl; with block_first a second thread asking during the first fill gets None. Tests join the refresh thread with wait() and inject the clock; test_calls.py sleeps up to 0.5 s with real children.
<!-- SECTION:NOTES:END -->
