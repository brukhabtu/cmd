---
id: TASK-1.35
title: plugins/index.toml and its CI check
status: In Progress
assignee: []
created_date: '2026-10-07 05:24'
updated_date: '2026-10-07 05:31'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 8. The index lists plugins by name with summary, source (git URL), ref (tag or commit) and optional subdirectory, and lists this repository's own plugins by subdirectory. CI checks the shape, that names are unique and match the manifest at the ref, and resolves every tag to the commit it points at, storing the commit beside it, since a tag can be moved after review.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The index lists calculator and websearch by subdirectory at a commit of this repository
- [ ] #2 CI fails on a malformed entry, a duplicate name, a missing ref, or a tag the check cannot resolve, and records each tag's commit
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. plugins/index.toml listing calculator and websearch by subdirectory at a commit of this repository, with name, summary, source and ref.
2. scripts/check_index.py, stdlib only: shape (required fields, known fields, unique names), a ref that is a commit or a tag, and for entries whose source is this repository the manifest at ref/subdirectory via git show, with the name matching; tags resolved with git ls-remote and their commits recorded beside them in a comment-free way (a 'commit' field the check fills and verifies).
3. A step in scripts/check.sh; tests in scripts/tests/test_check_index.py against a local git repository.
### Proof
uv run pytest scripts/tests; scripts/check.sh; a broken entry fails the step.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed: plugins/index.toml lists calculator and websearch by subdirectory at commit 1159f73 of this repository. scripts/check_index.py (stdlib and git) checks the shape without the network (required and known fields, strings, unique names, a tag needs its reviewed commit, commits are full hashes), then for each entry fetches the ref shallowly, reads cmd-plugin.toml at the subdirectory and compares the name, and for a tag resolves it with git ls-remote (peeling annotated tags) and compares with the recorded commit; a moved tag is reported and nothing else is fetched. scripts/check.sh runs it after the boundary step (1.8 s for the two entries, fetching by commit from GitHub). Tests: shape problems one by one, the entries against a local git repository with a tag, and the repository's own index. Not done here: 1.34's install must rewrite the in-repository plugins' cmd-sdk workspace source to the git source at the same ref, since 'workspace = true' cannot resolve outside the workspace; noted on 1.34. Awaiting review.
<!-- SECTION:NOTES:END -->
