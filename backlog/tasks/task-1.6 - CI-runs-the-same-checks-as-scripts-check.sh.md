---
id: TASK-1.6
title: CI runs the same checks as scripts/check.sh
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:58'
labels:
  - size-2
milestone: m-0
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 7000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An ubuntu job runs scripts/check.sh; a macOS job builds and clippies cmd-app
- [ ] #2 CI is green on the first pull request
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built in the foundation session. Complete and checked by the author; awaiting close by a reviewer who did not do the work, from the acceptance criteria and the evidence in scripts/check.sh.

Close-out review kept this open: CI had never run. ci.yml now runs on every push, so the branch gets a run without a pull request; the misleading pypeeker step was removed. Waiting on the first run.

First run (37564168447) on bb92a89: the ubuntu job failed in scripts/check.sh because CI's stable Rust was 1.99 and its clippy has assert_is_empty, which the 1.97 workstation did not; the macOS job was still building. Fixed the assertions, pinned the toolchain in rust-toolchain.toml so local and CI lints match, and pushed again.
<!-- SECTION:NOTES:END -->
