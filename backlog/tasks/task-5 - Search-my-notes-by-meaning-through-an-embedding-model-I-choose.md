---
id: TASK-5
title: 'Search my notes by meaning, through an embedding model I choose'
status: To Do
assignee:
  - '@brukhabtu'
created_date: '2026-10-10 16:15'
labels:
  - size-8
milestone: m-3
dependencies: []
type: intent
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
Keyword search (qmd's BM25, ripgrep) misses a note that says the same thing in other words. I want a search plugin that ranks by meaning, using an embedding model I pick, so "what did we decide about the offsite budget" finds the note that says "cost of the team trip". Nothing about the model may be fixed in code: I choose it, and can change it. The index it needs must build and refresh in the background, never on the keystroke path, and the launcher must stay responsive while it does (TASK-4).

## Open questions
- [ ] Which model runs, and where? A local model (an embeddings runtime such as llama.cpp, Ollama or sentence-transformers, through a command or a local HTTP endpoint) or a hosted API. Leaning: a provider kind per transport (`command`, `http`), the model name in config, so no model is named in code. Notes that leave the machine are the owner's call, and the default is local.
- [ ] Is this a new plugin, or new provider kinds for the search plugin (decision 11)? Leaning: the search plugin gains an `embeddings` kind, so merging, deadline, rests and the user page come free and a semantic provider can share a keyword with qmd. The index and the embedding work are the kind's own.
- [ ] Indexing: what is indexed (folders, globs), how it chunks, where the vectors live (the plugin's data directory, CMD_PLUGIN_DATA), how it learns of a change (file watch or a periodic scan by mtime), how a model change forces a re-embed, and how it resumes after a quit.
- [ ] Is indexing a capability every plugin can plug into, each in its own way? See the design task under this intent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Typing a configured keyword and a question shows notes ranked by meaning, and Enter opens the note
- [ ] #2 The model, its endpoint or command, and what to index come from a config file; no model name is in the code
- [ ] #3 Indexing runs in the background, survives a quit and a model change, and a query during indexing answers from what is indexed so far
- [ ] #4 Typing stays responsive while indexing runs and while the model is slow or down; a failing model shows a row, not a stall
- [ ] #5 The user page says how to point it at a local model, and what leaves the machine if a hosted one is chosen
<!-- AC:END -->
