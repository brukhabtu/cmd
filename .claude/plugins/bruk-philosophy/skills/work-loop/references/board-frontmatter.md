# Board frontmatter

What each frontmatter key means on the board, for the markdown the work loop uses:
tasks (an intent is a task), drafts, and decisions.

> Checked against Backlog.md 1.53.0 on a scratch board. The example files at the end are
> that board's real output. Not yet used on real work.

## The constraint

Backlog.md rewrites a task's frontmatter on every edit and keeps only the keys it knows.
A key added by hand is gone after the next `backlog task edit`. So this file defines no
new keys. It says what the existing keys mean here and which values are allowed.

Body sections written by hand do survive an edit.

## Tasks

| Key | Meaning here | Values | Enforced |
|---|---|---|---|
| `type` | What kind of node this is | `intent`, `design`, `spike`, `task`, `bug` | Yes. The CLI rejects a type that is not in `config.yml` |
| `status` | Where the node is in the loop | `Draft`, `To Do`, `In Progress`, `Done` | Yes |
| `labels` | Size | `size-1`, `size-2`, `size-3`, `size-5`, `size-8` | No. The CLI accepts any label |
| `assignee` | Who answers for the node | On an intent, the person with the problem. Otherwise, whoever is doing the work | No |
| `parent_task_id` | The node above it | Set with `-p` | Yes |
| `dependencies` | What blocks it | Set with `--dep` | Yes |
| `references` | What the node produced | On a design task, the path to its decision | No |
| `modified_files` | The plan's "files that change" | Set with `--modified-file` | No |

`id`, `created_date`, `updated_date`, and `ordinal` belong to the tool.

The four statuses read as:

- `Draft`: written down, not accepted. The file sits in `backlog/drafts/`.
- `To Do`: accepted. It can start once its dependencies are done.
- `In Progress`: someone is doing it.
- `Done`: closed by someone who did not do the work.

## Body sections

| Section | What goes in it |
|---|---|
| Description | On an intent: `## Problem`, then `## Open questions` as checkboxes. An unchecked box is a question still open |
| Acceptance Criteria | The outcome, and each thing that must not break, written so a reviewer can check it |
| Implementation Plan | On a leaf: `### Order of work`, `### Risks`, `### Proof`. The files go in `modified_files` |
| Implementation Notes | The worker's report |

## Accepting

A draft is a node nobody has accepted. `backlog draft promote` moves it from
`backlog/drafts/` to `backlog/tasks/` and sets it to `To Do`. The commit that does this
is the record of who accepted it and when. There is no key for it.

Promotion changes the id from `DRAFT-n` to `TASK-n`, so nothing should refer to a draft
by its id.

## Decisions

| Key | Meaning here | Values | Enforced |
|---|---|---|---|
| `id`, `title`, `date` | The tool's | | Yes |
| `status` | Where the decision stands | `proposed`, `accepted`, `rejected`, `superseded` | No. The tool takes any text and defaults to `proposed` |

A design task points at its decision through `references`.

## Config

`types` cannot be set with `backlog config set`. Edit `backlog/config.yml`:

```yaml
types: ["intent", "design", "spike", "task", "bug"]
labels: ["size-1", "size-2", "size-3", "size-5", "size-8"]
```

`backlog task list --type intent` then lists every intent.

## What has no key

- **Who wrote it, who accepted it, and when.** Git history has all three.
- **How many questions are open.** Counted from the checkboxes in the body.
- **Whether the finish line moved after work started.** Git history of the Acceptance
  Criteria block.
- **Exactly one valid size label.** The tool does not check labels, so this needs a
  script. Not built.

## Example

An intent, before anyone has accepted it (`backlog/drafts/`):

```markdown
---
id: DRAFT-1
title: Claims status self-service
status: Draft
assignee:
  - '@j.ortiz'
created_date: '2026-10-06 22:08'
labels:
  - size-5
dependencies: []
type: intent
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
Customers phone the contact centre to ask where their claim is. Handlers spend roughly a third of call time on status-only queries.

## Open questions
- [ ] Do third-party loss adjusters need access too?
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Customers see claim status, next step and expected date in the portal
- [ ] #2 No new PII in the portal session
- [ ] #3 Existing authentication only
<!-- AC:END -->
```

A design task under it, pointing at its decision:

```markdown
---
id: TASK-1.1
title: Decide how the portal stays under the claims-core rate limit
status: To Do
assignee: []
created_date: '2026-10-06 22:08'
labels:
  - size-2
dependencies: []
references:
  - backlog/decisions/decision-1 - Cache-claim-status-in-the-portal.md
parent_task_id: TASK-1
type: design
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded
<!-- AC:END -->
```

A leaf with its plan, blocked on the design task:

```markdown
---
id: TASK-1.2
title: Status endpoint behind existing auth
status: To Do
assignee: []
created_date: '2026-10-06 22:08'
updated_date: '2026-10-06 22:08'
labels:
  - size-3
dependencies:
  - TASK-1.1
modified_files:
  - claims-api/routes/status.py
  - claims-api/tests/test_status.py
parent_task_id: TASK-1
type: task
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 test_status.py covers the four claim states
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Add the status endpoint behind existing auth.
2. Cache responses per the decision.

### Risks
The claims-core API rate-limits at 50 rps.

### Proof
test_status.py covers the four claim states.
<!-- SECTION:PLAN:END -->
```

The decision it waits on:

```markdown
---
id: decision-1
title: Cache claim status in the portal
date: '2026-10-06 22:08'
status: proposed
---
## Context

## Decision

## Consequences
```
