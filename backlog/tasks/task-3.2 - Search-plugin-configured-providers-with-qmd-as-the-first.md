---
id: TASK-3.2
title: 'Search plugin: configured providers, with qmd as the first'
status: To Do
assignee: []
created_date: '2026-10-09 13:51'
labels:
  - size-5
milestone: m-3
dependencies:
  - TASK-3.1
parent_task_id: TASK-3
type: task
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A new plugin under plugins/search, built as the design decision says: the provider interface, the qmd kind and the generic command kind, several providers merged under one keyword, tested with fixtures captured from the real qmd and a fake provider executable. The real qmd was installed for the spike at scratchpad/qmd-real on the lead's machine; its outputs are quoted on TASK-3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A configured keyword and text shows qmd's hits ranked best first, and Enter opens the note, from config alone
- [ ] #2 Two providers sharing a keyword are searched together and merged, and a failing or slow one shows its message beside the other's hits
- [ ] #3 query never raises and answers inside the host's timeout; a first word that is no keyword starts no process
- [ ] #4 Fixtures captured from the real qmd run through the plugin in a contract test, and a test against an installed qmd runs when one is named in the environment and is skipped otherwise
- [ ] #5 docs/use has a page for the plugin, the plugin is in the index and the generated references, and scripts/check.sh passes
<!-- AC:END -->
