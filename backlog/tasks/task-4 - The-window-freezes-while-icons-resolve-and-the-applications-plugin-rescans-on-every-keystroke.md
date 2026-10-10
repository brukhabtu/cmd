---
id: TASK-4
title: >-
  The window freezes while icons resolve, and the applications plugin rescans on
  every keystroke
status: In Progress
assignee: []
created_date: '2026-10-10 16:12'
updated_date: '2026-10-10 16:16'
labels:
  - size-2
dependencies: []
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reported by the owner: the UI freezes in two situations. (1) IconAsset::load asked AppKit (NSWorkspace iconForFile, TIFF to PNG) on the main thread for every icon not yet cached, up to eight per keystroke; fixed by running it on the background executor, one AppKit call at a time. (2) plugins/applications walked every root on each keystroke (DRAFT-11); fixed with a 30 s TtlCache warmed at start. Plugin calls were already off the UI thread (TASK-1.11) and the host answers only the newest query, so a slow plugin delays rows and never the window. Owed on the Mac: type quickly in the launcher with a cold icon cache and see no stutter.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Typing does not call AppKit or walk the disk on the main thread; applications scans at most once per 30 s
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Related: TASK-5 (semantic search) and its design task, indexing as a plugin capability.
<!-- SECTION:NOTES:END -->
