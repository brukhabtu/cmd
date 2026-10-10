---
id: TASK-5.1
title: 'Design: indexing as something any plugin can offer the host'
status: To Do
assignee:
  - '@brukhabtu'
created_date: '2026-10-10 16:16'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-5
type: design
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Question
Search by meaning (TASK-5) needs an index built in the background. Vault (decision 10) has an outbox it drains, search/qmd rely on qmd's own index, the applications plugin rescans a cache (TASK-4), and files leans on Spotlight. Each has some kind of background upkeep, done differently. Should the protocol let a plugin declare it, so the host can show and steer it?

## What the host would gain
- One place to show it: a plugin that is indexing says so (what, how far), and the window shows the spinner DRAFT-4 describes instead of each plugin faking a row.
- Control: a Rebuild action per plugin, a pause while on battery or while the person is typing, and the same behaviour after a quit.
- Honest failure: an index that cannot build is a visible state, not a silent empty result.

## What must stay the plugin's
How: chunking, the model, the store, the change detection. The host never learns what an index is; it learns a state.

## Leaning
Yes, but small, and as a capability under decision 9's rules (an optional capability, protocol stays 1): `index` in `describe` capabilities. The plugin owns its own thread (as vault and search already do) and the SDK gives it a helper to report `{state: idle|building|failed, done, total, message}`. The host asks for it with a cheap `status` method (answered from memory, never waiting on the build) and sends a `reindex` request that returns at once. No host-driven indexing loop: a protocol call has a 3 s timeout and an index build does not. Query never waits for the build.

## Open questions
- [x] Poll or push? Push: the plugins report (the owner, 2026-10-10). The plugin sends a line that answers no request whenever its index state changes. That asks the protocol for a plugin-to-host notification (a message with no id), which is a new capability under decision 9, and the host's reader and the SDK's `serve` both change. Still to settle in the decision: how often a plugin may report (a rate limit, so a build cannot flood the window), whether the host keeps only the latest state per plugin, and what the host shows for a plugin that built and then went quiet.
- [ ] Does the host schedule (battery, idle, quiet hours) or only display? Leaning: display and trigger first; scheduling policy later.
- [ ] Which plugins would use it today: vault (outbox), search (embeddings kind), applications (scan)? A contract that fits none of them but search is a smell.
- [ ] Where does an index live? CMD_PLUGIN_DATA already exists; does the host need to know its size to offer "clear index"?

## Output
A decision, then the capability in the protocol, the SDK helper and the host, as separate tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision records whether indexing is a capability, its methods and states, push or poll, and which existing plugins would adopt it
- [ ] #2 The decision says what a plugin must do so that a build never blocks a query or the window
<!-- AC:END -->
