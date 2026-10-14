---
id: TASK-2.9
title: Several keywords and a home query for blank input
status: To Do
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-14 19:57'
labels:
  - size-3
dependencies:
  - TASK-2.3
parent_task_id: TASK-2
type: task
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Optional `describe` fields: `keywords` (several) and a flag that a plugin wants blank input, which the host sends as {"text": "", "home": true}. A keyword that two plugins claim is reported like a duplicate plugin name, not silently dropped. Once this lands the vault plugin drops its own keyword matching.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A plugin with several keywords is reached by each, and an old host treats it as it did before
- [ ] #2 Blank input reaches the plugins that asked for it and nobody else
- [ ] #3 A keyword clash is shown in the window
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: decision 13 needs only the home query from this task (the home flag); that piece ships first as part of TASK-6, several keywords stay here.

2026-10-14: the home-query half is built and closed on review by a read-only reviewer who did not do the work (describe home flag, route_home, Host::home, Step::Home, SDK Plugin.home, docs and golden fixture). The several-keywords half is still open. Known gap: a home plugin that restarts or reloads while the input is blank is asked again only on the next show or edit.
<!-- SECTION:NOTES:END -->
