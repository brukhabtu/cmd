---
id: TASK-1.22
title: 'Design: how a bundle finds or carries uv and Python 3.15'
status: In Progress
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 05:26'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-1
type: design
ordinal: 23000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision picks between requiring uv on PATH, bundling uv, and bundling a Python, with first-launch time and bundle size measured
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Measure here (Linux container, stated as such): the uv binary's size, a uv-managed CPython 3.15's size on disk, a plugin's own environment, and the first and second 'uv run' of a plugin copied outside the workspace with a cold uv cache.
2. Decision 7 weighs three ways for cmd.app to run plugins: uv on PATH, uv inside the bundle, a Python inside the bundle; picks one for 1.23 and says what would change the choice.
### Proof
The decision carries the numbers and how they were taken; the reviewer checks the reasoning.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Decision 7 written: cmd.app carries uv and nothing else; uv manages one Python under ~/Library/Application Support/cmd/ (UV_PYTHON_INSTALL_DIR, UV_CACHE_DIR, UV_PYTHON_PREFERENCE=only-managed), the host puts the bundle's directory first on the plugins' PATH so 'uv run' in a manifest resolves to the bundled binary. Measured here (Linux x86_64, uv 0.11.32, stated in the decision): uv 66 MB; a managed CPython 3.15 5.1 s to fetch and 111 MB on disk; the websearch environment 236 KB; first uv run with a Python present 0.25 s, then 0.13 and 0.07 s. The Mac figures (arm64 uv, download on a home connection, first launch of each bundled plugin) are owed before 1.23 closes, not before this decision. Awaiting review.

Reviewer at 79d4c47: KEEP OPEN, the two figures the criterion names were assembled, not measured end to end; cmd-doctor must not inherit only-managed; the window cannot say 'fetching Python' while start_host runs before the window exists. Done since: measured end to end on this container with both plugins outside the workspace through cmd-doctor one after the other, no managed Python, cold cache: 5.8 s with an explicit 'uv python install 3.15', then 0.34 s warm, 0.06 s for the install when present; each plugin environment 192 KB. Finding: with only-managed and no Python, 'uv run' refuses to fetch a version its embedded list does not know (3.15 was a pre-release for this uv), so the decision now has the app run 'uv python install 3.15' explicitly before the first plugin. The environment is applied only inside a bundle; cmd-doctor and a clone use the developer's own. TASK-1.32 filed for opening the window before the host starts. A release build of the app is running for the bundle total.

Bundle total added from a release build of the app in the Linux scratch workspace: cmd 26 MB, uv 66 MB, so 92 MB for the bundle and 204 MB with a Python inside as well. Awaiting review.
<!-- SECTION:NOTES:END -->
