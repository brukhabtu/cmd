---
id: TASK-1.4
title: 'Philosophy plugin and cmd-dev plugin wired in, with the skill gate'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
labels:
  - size-2
milestone: m-0
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 5000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 .claude/settings.json enables philosophy@bruk-philosophy and cmd-dev@cmd-dev from the vendored directories
- [ ] #2 claude plugin validate --strict passes for both, and the philosophy hook's own tests pass from the vendored location
- [ ] #3 docs/skills.md states when skills are proposed and the eval gate they must pass; .github/workflows/skills.yml runs it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built in the foundation session. Complete and checked by the author; awaiting close by a reviewer who did not do the work, from the acceptance criteria and the evidence in scripts/check.sh.
<!-- SECTION:NOTES:END -->
