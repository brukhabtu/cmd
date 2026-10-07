---
id: TASK-1.32
title: Start the host off the main path so the window opens before the first describe
status: To Do
assignee: []
created_date: '2026-10-07 05:20'
labels:
  - size-2
milestone: m-2
dependencies: []
parent_task_id: TASK-1
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
main() in crates/cmd-app/src/main.rs runs start_host before Application::new, and Host::start blocks on each plugin's describe for up to 60 s, so on a first launch the window does not exist until every handshake, including uv's one-time Python download under decision 7, has finished. Open the window first and start the host on a background task, reporting each plugin as it comes up, so the window can say what it is waiting on. From the review of task 1.22.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The window is on screen before any plugin has described itself, and says which plugins are still starting
- [ ] #2 A plugin whose first start fails is reported in the window as 1.30 does, not only on stderr
<!-- AC:END -->
