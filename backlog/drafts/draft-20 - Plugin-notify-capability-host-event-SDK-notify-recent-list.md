---
id: DRAFT-20
title: 'Plugin notify capability: host event, SDK notify(), recent list'
status: Draft
assignee: []
created_date: '2026-10-14 18:32'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-6
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decision 13. Needs DRAFT-15 (the reader that classifies lines as they arrive, the SDK locked writer, the capabilities machinery). The notify line and the host naming notify in capabilities; HostEvent::Notify; SDK notify() callable from any thread, silent when the host did not name it; the host cleans text, drops notices above a rate, keeps the last twenty in a recent list. Docs and golden fixture.
<!-- SECTION:DESCRIPTION:END -->
