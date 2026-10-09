---
id: DRAFT-14
title: A warm qmd server as a provider kind (qmd-http) for qmd's slow modes
status: Draft
assignee: []
created_date: '2026-10-09 19:07'
labels:
  - size-3
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up from decision 11, not a blocker for TASK-3. qmd's vsearch and query load models per process and stay off the as-you-type path. They may join it only if all four hold: (1) a warm `qmd mcp --http --daemon` that the person or launchd starts; (2) a `qmd-http` kind that POSTs to localhost:8181/query with a timeout from the plugin's own process and shows a stopped daemon (GET /health) as a row; (3) on the owner's Mac the p95 of /query over his notes, rerank on and off and including the recreation after idle, is at most half the deadline; (4) the kind finds paths, since the HTTP answer carries qmd:// URIs only. Even then it belongs on a keyword shared with a `search` provider. Blocked on the Mac measurements and on decision 11 being accepted.
<!-- SECTION:DESCRIPTION:END -->
