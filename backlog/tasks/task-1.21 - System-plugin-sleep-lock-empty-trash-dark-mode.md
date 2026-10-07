---
id: TASK-1.21
title: 'System plugin: sleep, lock, empty trash, dark mode'
status: In Progress
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 07:11'
labels:
  - size-2
milestone: m-3
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 22000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each command is an item with a definite answer; Enter performs it and hides
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
A third plugin, plugins/system, in the calculator's shape: commands.py is pure data and prefix matching; __init__.py runs one fixed argv per command and maps the outcome to Close or Show. No keyword, items without a score so the command ranks above fuzzy rows; Enter runs and returns close. Executor injected for tests, real subprocess tests harmless on any platform, a cmd-host adapter test that runs an unknown item so no Mac is ever put to sleep by cargo test. No protocol change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: plugins/system (manifest, pyproject, commands.py pure data and prefix matching with MIN_PREFIX 2, __init__.py runs one fixed argv per command through an injectable executor and answers Close or Show), its unit and functional tests, crates/cmd-host/tests/system.rs through the real process, root pyproject (mypy_path, testpaths, pypeeker src and allow row, a per-file ruff ignore for the subprocess rules), uv.lock, README plugins row. Protocol untouched.

Where the code contradicted the plan: a second keywordless plugin makes a query reach both calculator and system, and crates/cmd-host/tests/calculator.rs matched the next event blindly, so it failed 5 of 6 runs once system existed. Two helpers in tests/common/mod.rs (answer_from, effect_from) wait for the named plugin's event and skip other plugins' answers; both adapter tests use them and pass 6 of 6. Also, after PATIENCE the child's stderr is drained by a daemon thread rather than closed, so a chatty child is never killed by EPIPE.

Evidence: scripts/check.sh all checks passed (exit 0); pytest 100 passed (29 of them the system plugin's); cargo test -p cmd-host --test calculator --test system six times, ok each; clippy -D warnings clean; mutation MIN_PREFIX=1 fails 2 tests, restored passes 29; cmd-doctor plugins/system --query lock --run sleep prints the one Lock screen item and {kind: show, text: Sleep needs macOS}.

Owed: plugins/index.toml entry for system pinned to this commit once it is pushed (CI's check_index fetches the manifest at the ref). On a Mac: ls the CGSession path; cmd-doctor --query lock --run lock prints {kind: close} and the screen locks; in the app dark, trash and sleep each perform on Enter and hide, allowing the Automation prompt the first time. If CGSession is gone, LOCK's argv becomes (/usr/bin/pmset, displaysleepnow). Note for 1.23: the bundle's Info.plist needs NSAppleEventsUsageDescription or Finder and System Events refuse without a prompt.
<!-- SECTION:NOTES:END -->
