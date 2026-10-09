---
id: TASK-3
title: 'Search my notes and documents from the launcher, through providers I choose'
status: In Progress
assignee:
  - '@brukhabtu'
created_date: '2026-10-09 13:51'
updated_date: '2026-10-09 14:58'
labels:
  - size-5
milestone: m-3
dependencies: []
type: intent
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
My notes, meeting transcripts and docs are indexed by qmd (https://github.com/tobi/qmd, a local search engine: BM25, vectors and reranking over markdown). I want to reach a note from the launcher as fast as I reach an app, and I do not want the launcher tied to one search tool: other providers (a ripgrep over a folder, another index) should plug in the same way, and I should be able to search several at once.

## Open questions
- [x] One plugin with configured providers, or one plugin per tool? One plugin, `search`, configured with providers, as draft 8 argues for feeds; a provider kind is a small piece of code, plus a generic `command` kind so a tool needs no code at all.
- [x] Do several providers answer one typed word? Yes: providers that share a keyword are searched together, in parallel under one deadline, and their hits are merged and ranked.
- [ ] Does qmd's slow hybrid mode (`qmd query`: query expansion and reranking with local models) belong on the as-you-type path? Leaning: no. `qmd search` (BM25) answers in about 0.25 s warm; the others load models and are measured on the Mac before they get a keyword.

## What the qmd spike found (the lead, 2026-10-09, qmd 2.8.3 run for real on Linux)
- `qmd search "<text>" --json -n N [-c <collection>]... [--full-path] [--index <name>]` prints a JSON array. Each hit: `{"docid": "#75ebe1", "score": 0.49, "file": "qmd://notes/offsite.md", "line": 1, "title": "...", "context"?: "...", "snippet": "@@ -1,3 @@ (0 before, 1 after)\n# Title\n\nbody text"}`. No hits: `[]`, exit 0. With `--full-path` `file` is the on-disk path, absolute unless the file is under the working directory, when it is `./relative` (resolve it against the working directory) and `docid` is left out.
- `score` is `|bm25|/(1+|bm25|)` (checked in qmd's source by the design worker) and not trustworthy across queries: in a three-note corpus a clear match scored 0 and another 0.49. Rank order is the signal.
- The snippet opens with a diff-style header line (`@@ -1,3 @@ (...)`) that must be dropped before showing it.
- Warm `qmd search` takes about 0.23 s. Errors are exit 1 and one stderr line: `Collection not found: nosuchcollection`, and `Usage: qmd search [options] <query>` for an empty query or one that starts with `-` (put `--` before the query).
- The `qmd` launcher is `#!/usr/bin/env node`, so from a Dock launch (a bare PATH) it fails with exit 127 and `env: 'node': No such file or directory`. A provider needs an absolute binary and a PATH it hands to the process (`/usr/bin/env PATH=... <bin> ...`).
- Collections and their roots live in `~/.config/qmd/index.yml`; `qmd collection list` is prose, not JSON.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Typing a configured keyword and some text shows qmd's hits, best first, and Enter opens the note
- [x] #2 More than one provider can be configured; providers that share a keyword are searched together and merged, and one that fails or is slow shows its message without hiding the others' hits
- [x] #3 Every value comes from a config file: binary, PATH, collections, keywords; no qmd path or collection name is in the code, and a provider that is not qmd needs no code
- [x] #4 query never raises and answers inside the host's timeout however many providers are slow; a keystroke that is no keyword costs nothing
- [x] #5 A contract test runs fixtures captured from the real qmd through the plugin, and a fake provider covers the failure modes
- [x] #6 The plugin's user page says how to configure qmd and a second provider, and scripts/check.sh passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-09: TASK-3.1 and TASK-3.2 are Done, closed on review. Acceptance criterion 1 (Enter opens the note) is shown on Linux with an Open effect and a real qmd; what a Mac does with it (qmd installed there, the Dock launch's bare PATH and the absolute bin and env.PATH, Open and Reveal in Finder, the obsidian:// open template, a cold search's timing) is the checklist on TASK-3.2, and closes this intent. Open question: qmd's slow modes (query, vsearch) stay off the as-you-type path until they are measured on the Mac with their models; decision 11 lists what would have to be true for them to join. Decision 11 is proposed: its assumptions (the status keyword search, the 1.0 s deadline, the cache and rest numbers, problem rows after the hits) are the owner's to confirm.
<!-- SECTION:NOTES:END -->
