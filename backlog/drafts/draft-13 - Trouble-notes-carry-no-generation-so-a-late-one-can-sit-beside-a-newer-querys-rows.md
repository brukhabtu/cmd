---
id: DRAFT-13
title: >-
  Trouble notes carry no generation, so a late one can sit beside a newer
  query's rows
status: Draft
assignee: []
created_date: '2026-10-08 20:46'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the review of TASK-2.3: HostEvent::Trouble (used to say that items were left out of an answer) has no generation, so a note about an old query can appear beside the rows of a newer one, under the old plugin's name, and it takes the window's only message slot, which can hide another plugin's failure message. Wrong notes, never wrong rows. Give Trouble the query generation as results have, drop a stale one, and let the window keep more than one message. crates/cmd-app/src/main.rs, crates/cmd-core/src/state.rs, crates/cmd-host/src/host.rs.
<!-- SECTION:DESCRIPTION:END -->
