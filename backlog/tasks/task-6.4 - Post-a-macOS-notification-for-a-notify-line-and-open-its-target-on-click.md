---
id: TASK-6.4
title: 'Post a macOS notification for a notify line, and open its target on click'
status: To Do
assignee: []
created_date: '2026-10-14 18:32'
updated_date: '2026-10-14 19:58'
labels:
  - size-2
milestone: m-3
dependencies:
  - TASK-6.1
  - TASK-6.3
parent_task_id: TASK-6
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 13. Follows the spike and the notify task. Delivery only; the recent list already holds the notice if delivery fails. Owed on the Mac.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the TASK-6.3 review (must be settled before click-to-open ships): a notice's open target arrives unprompted from a background plugin, and the Open effect (crates/cmd-app/src/main.rs, cx.open_url) applies no scheme check, so a plugin could open file:// apps or scripts, custom URL handlers (ssh:, vnc:, other apps' deep links) or lookalike links. Leaning: allow https, http and mailto by default; refuse file: and custom schemes unless the plugin's cmd-plugin.toml declares them; show the host in the notification; cap open at 2 KB in the host (drop the notice if longer; Recent keeps 20 of them for the life of the app). Ideally the same check covers the existing Open effect.
<!-- SECTION:NOTES:END -->
