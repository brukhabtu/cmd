---
id: TASK-1.18
title: 'SDK tutorial: a plugin in ten minutes'
status: In Progress
assignee: []
created_date: '2026-10-07 02:40'
updated_date: '2026-10-07 04:39'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 19000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A newcomer follows python/cmd-sdk/README.md from an empty directory to a working keyword plugin without reading the Rust
- [ ] #2 The tutorial's plugin is checked in under plugins/ and covered by the adapter test
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. A second plugin, websearch: keyword 'web', fuzzy-free items with a score, two actions (open the search, copy the URL), an Open effect. Small enough to read in one sitting, so it is the tutorial's subject.
2. The tutorial in python/cmd-sdk/README.md walks from an empty directory to that plugin.
3. The adapter test drives it through the host: keyword routing, items, run with each action.
### Risks
None technical; the tutorial is prose a newcomer has to follow, which only a newcomer proves.
### Proof
uv run pytest, cargo test -p cmd-host --test calculator.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented: plugins/websearch (keyword 'web', two actions, Open and Copy effects) with unit tests; python/cmd-sdk/README.md is the ten-minute tutorial built on it, from the three files to cmd-doctor and installing; the host adapter test proves keyword routing, the stripped text, both actions and that a global query never reaches a keyword plugin. Only a newcomer can prove the prose. Awaiting review.
<!-- SECTION:NOTES:END -->
