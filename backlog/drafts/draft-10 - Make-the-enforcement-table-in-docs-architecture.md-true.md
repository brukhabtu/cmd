---
id: DRAFT-10
title: Make the enforcement table in docs/architecture.md true
status: Draft
assignee: []
created_date: '2026-10-08 13:47'
labels:
  - size-1
dependencies: []
parent_task_id: TASK-2
type: task
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The page says std::process, std::fs and std::net are disallowed in cmd-core; crates/cmd-core/clippy.toml lists specific items and misses read_dir, OpenOptions, env::var_os, env::args, Instant::now, thread::spawn, TcpListener and println!. The core is clean today. Widen the list or reword the page. The LikeC4 host to core edge says the host merges results; the state machine does.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 clippy.toml and the page agree, and the LikeC4 edge is corrected
<!-- AC:END -->
