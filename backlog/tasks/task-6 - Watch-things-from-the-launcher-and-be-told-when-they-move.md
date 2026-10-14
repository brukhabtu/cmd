---
id: TASK-6
title: Watch things from the launcher and be told when they move
status: In Progress
assignee:
  - '@brukhabtu'
created_date: '2026-10-14 18:32'
updated_date: '2026-10-14 20:36'
labels:
  - size-8
milestone: m-3
dependencies: []
type: intent
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
I want to watch a ticket or a pull request and know when it moves, without opening the service. The launcher is hidden most of the time, so a watcher has to tell me while it is hidden, and show me what moved when I open it. Jira is only the example: the protocol work is the point, proved by a demo plugin with no network.

## Open questions
- [ ] Decision 13 (proposed): watch is an action on an item and the host knows no watch; `complete` and Tab; a `notify` capability; the home query. The owner confirms its assumptions.
- [ ] Does a notification from an unsigned build show under cmd's name? Checked on the Mac (spike).
- [ ] Where do secrets live for a real Jira or GitHub plugin? Not needed by the demo; Keychain through `security` is the leaning.
- [ ] The `>` verbs mode across plugins: deferred.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A demo plugin lets me pick a ticket, choose Watch, and get a macOS notification when its status changes in the watched file, with the window hidden
- [ ] #2 Tab completes a row's text and a plugin with nothing to complete is unaffected
- [ ] #3 Opening the window with blank input shows what moved while I was away
- [ ] #4 A broken watch shows once as a task and does not notify on every poll
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Plan (decision 13): the Mac notification spike first (owner-run, it decides delivery); DRAFT-15 (decision 12's reader and writer) in parallel with the complete/Tab task and DRAFT-5 (home query); then the notify capability; then macOS delivery; then watchdemo; then the user page. complete and the home query do not depend on the reader work. Follow-ups, not in scope: the > verbs mode, secrets for a real Jira plugin, watchers as a feeds provider (DRAFT-8).

2026-10-14: built and closed on review: 6.2 (complete, Tab), 6.3 (notify), 6.5 (watchdemo), with TASK-7, 8, 9 and the home half of 2.9. Also built, reviewed inside 6.5's review: recent notices on the home list. Left: 6.1 (Mac spike) and 6.4 (macOS delivery) need the owner's Mac; 6.6 the user page.
<!-- SECTION:NOTES:END -->
