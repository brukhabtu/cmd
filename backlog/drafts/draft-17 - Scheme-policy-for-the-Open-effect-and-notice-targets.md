---
id: DRAFT-17
title: Scheme policy for the Open effect and notice targets
status: Draft
assignee: []
created_date: '2026-10-14 19:58'
labels:
  - size-3
dependencies: []
type: design
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the TASK-6.3 review. The Open effect passes any plugin string to cx.open_url with no scheme check. Decide the policy (leaning: https, http, mailto by default; file: and custom schemes only when the plugin's manifest declares them), what the person sees when one is refused, and apply it to Open and to a notice's open target (TASK-6.4). Existing plugins open file:// URLs of apps (applications) and paths (files): the manifest declaration must cover them without a prompt.
<!-- SECTION:DESCRIPTION:END -->
