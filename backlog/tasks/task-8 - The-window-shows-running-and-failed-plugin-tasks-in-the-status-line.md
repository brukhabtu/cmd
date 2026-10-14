---
id: TASK-8
title: The window shows running and failed plugin tasks in the status line
status: Done
assignee: []
created_date: '2026-10-10 18:30'
updated_date: '2026-10-14 19:57'
labels:
  - size-3
milestone: m-3
dependencies:
  - TASK-7
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 12. Shares the status line with start trouble (TASK-1.39). Running tasks show label and done/total; done shows for a few seconds; failed stays until dismissed. Redraw at most every 250 ms. Depends on the protocol task.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: closed on a second review (the first blocked it: a failure could be dismissed unseen; fixed so a failure counts as seen only when it is the text on the line, and a hidden window counts as covered). Owed on the Mac: the line, colours, truncation, 250 ms coalescing and expiry redraw in the real window. Open: whether a dismiss key is wanted (decision 4 owns the keys); today a failed task is dismissed by hiding the window after it was drawn.
<!-- SECTION:NOTES:END -->
