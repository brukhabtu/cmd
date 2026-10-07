---
id: TASK-1.4
title: 'Philosophy plugin and cmd-dev plugin wired in, with the skill gate'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 02:53'
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

Close-out review kept this open: the marketplace paths in .claude/settings.json may not resolve, and skills.yml did not match docs/skills.md. The workflow now runs the whole suite with ablation and scripts/eval_gate.py fails any case whose delta is not positive; the document says exactly that. The path question is answered in the notes below once verified.

Settings paths verified against the Claude Code binary (v2.1.292): a directory marketplace source is resolved with path.resolve against the project directory, not the settings file, so ./plugins/... was wrong. Fixed to ./.claude/plugins/bruk-philosophy and ./.claude/plugins/cmd-dev. Ready for re-review.
<!-- SECTION:NOTES:END -->
