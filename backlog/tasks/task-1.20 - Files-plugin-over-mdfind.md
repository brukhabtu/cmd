---
id: TASK-1.20
title: Files plugin over mdfind
status: In Progress
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 07:03'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 21000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Keyword 'f' searches with mdfind and returns paths with their parent folder as subtitle
- [ ] #2 Enter reveals in Finder; a second action opens the file
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
A keyword plugin (f) in the websearch shape. plugins/files/src/files/search.py is pure: mdfind arguments, NUL parsing, ranking, parent folder, file URL. __init__.py is the shell: mdfind under a 2 s deadline, open -R for reveal then Close, Open(file URL) for the second action. Unit tests for the pure module, functional tests with fake mdfind and open sh scripts on PATH, and a Rust adapter test crates/cmd-host/tests/files.rs through the real uv-run process with the fakes on a PATH prefix. Root pyproject gains the plugin paths and the lock is regenerated. No protocol change, no cmd-app change. The index entry is owed once the branch is on GitHub.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: plugins/files (cmd-plugin.toml, pyproject.toml, src/files/search.py pure, src/files/__init__.py shell), unit tests for the pure module, functional tests with fake mdfind and open sh scripts on PATH, crates/cmd-host/tests/files.rs through the real uv-run process with the fakes on a PATH prefix via env, root pyproject.toml entries (mypy_path, testpaths, pypeeker src and allow, a per-file ignore for subprocess), uv.lock regenerated. No protocol change, no cmd-app change. Enter runs open -R itself and answers close; the second action answers open with a file:// URL (Path.as_uri), since cmd-app hands the target to GPUI open_url, which needs a scheme on macOS. Evidence on Linux: uv run pytest -q plugins/files/tests -> 27 passed; cargo test -p cmd-host --test files -> 1 passed; clippy pedantic clean; scripts/check.sh -> all checks passed (98 pytest, index check against the network). Owed to a person on a Mac: run the app, type f readme, see rows with their folders, press Enter and watch Finder reveal; then cmd-doctor on plugins/files with --query readme --run <a path> --action open and confirm the file opens; judge whether a one-letter query lags (a two-character minimum is a one-line change). Also owed: the plugins/index.toml entry for files pinned to this change once the branch is on GitHub (the check fetches the ref); the README plugin row; and a size-1 follow-up so cmd-app converts a bare path to a file URL, which 1.19 needs too.
<!-- SECTION:NOTES:END -->
