---
id: TASK-1.6
title: CI runs the same checks as scripts/check.sh
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 03:08'
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

Run 2 (https://github.com/brukhabtu/cmd/actions/runs/37564566819) on 5fc99d0: the ubuntu job ran scripts/check.sh green in 57 s (fmt, clippy, tests including the adapter test through uv, ruff, mypy, pytest, the functional suite twice, pypeeker strict, likec4 validate, both plugin validations, the hook tests). The macOS job passed cargo clippy -p cmd-app -D warnings at 03:03 and was building the app when this note was written; run 1's macOS job (https://github.com/brukhabtu/cmd/actions/runs/37564168447) built cmd-app green on bb92a89. There is no pull request yet, so 'green on the first pull request' is evidenced by the branch runs.
<!-- SECTION:NOTES:END -->
