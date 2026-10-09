---
id: TASK-3.1
title: 'Design: the search plugin''s providers, config and merging'
status: Done
assignee: []
created_date: '2026-10-09 13:51'
updated_date: '2026-10-09 14:06'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-3
type: design
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Settle before any code, since a config format is hard to change once people write it. One plugin, `search`, configured with providers. Decide, in one decision (the next number is 11), using the qmd findings on TASK-3:
- The provider interface in code (what a provider kind is given and returns, so a new kind is a small module) and the generic `command` kind (a user-supplied command and how its output is read), including how a provider's hits are ranked when its own scores cannot be trusted.
- The config TOML: providers, their keywords (providers may share one), the binary as an absolute path, the PATH handed to the process, collections, limits and deadlines, with a worked example for qmd and for a second provider. What the plugin shows for a missing or invalid config.
- How providers that share a keyword are searched together: parallel under one deadline shorter than the host's, merged and ranked, duplicates (the same file from two providers) collapsed, the provider named in each row, and what a failing or slow provider shows without hiding the others.
- How the plugin matches its own keywords until the protocol has several (decision 10 does the same for the vault), and the as-you-type cost: a word that is no keyword costs nothing, and what keeps a process from being started on every keystroke.
- What Enter and the other actions do with a hit: open the note, copy its path, anything the effects allow; and what a hit with no resolvable path does.
- Whether qmd's slow modes (query, vsearch) can ever be on the query path, and what would have to be true for them to be.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One decision records the provider interface, the config schema with a worked example for qmd and for a second provider, and how providers that share a keyword are merged
- [x] #2 The decision says what a failing, slow or missing provider shows, and that query never raises and stays inside the host's timeout
- [x] #3 The decision says how Enter, the other actions and a hit without a path behave
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Wrote decision 11 (backlog/decisions/decision-11 - The-search-plugins-providers-config-and-merging.md), proposed. It settles: the kind interface (a module with KEYS, REFERENCE, parse, executable, arguments, read over Hit/Found/Failed) with qmd and command kinds; rank over score, providers interleaved by rank then config order, rows sent without a score; the config schema with a table of every key, a qmd plus ripgrep example and a smallest one (both parsed with tomllib); env handed over as /usr/bin/env K=V; config problems as rows; decision 10's own keyword matching; parallel calls under one deadline (default 1.0 s, at most 1.5) with query answering by deadline + 1 s, at most 2.5 s; min_chars, a 10 s cache per provider and text, and a 30 s rest after three timeouts; collapse by real path or URL; problem rows after the hits; Enter, Reveal, Copy path and Copy docid, and the rows for a hit not on disk; slow modes off the query path until four conditions hold; the 12 things task 3.2 tests.

Departure, recorded in the decision: decision 9 says a provider never runs in query. That fits feeds; a search provider's answer depends on the typed text, so it runs in query under this deadline. Decision 9 should say its rule is for feed providers (not edited here).

Assumptions (all in the decision): status keyword search; deadline 1.0 s; rank interleaving, no weights; min_chars 2, the 10 s cache and the 30 s rest; problem rows after the hits; the open template and its obsidian:// example, which is unverified; Copy docid only where qmd gives one, since --full-path drops it for files on disk; a .qmd/index.yml above the plugin directory would change qmd's index; a misspelt index is not detected; paths that differ only in case are not collapsed.

Verified by running the isolated qmd 2.8.3 from a scratch directory: warm search --json --full-path took 0.20 s median, 0.22 s p95, 0.24 s max over 20 runs; the decision's exact argv (-c twice, --index index, --) works; -x without -- is a usage error, -- -offsite answers []; FTS syntax in the text never errors; -c nosuch exits 1 with one stderr line; bare PATH exits 127, /usr/bin/env PATH=... answers; --index nosuchindex answers [] and creates an empty index (removed afterwards); qmd get <absolute path> reads a note and prints its URI and docid on its first line; the score is |bm25|/(1+|bm25|) (store.ts searchFTS), not normalised per result set as TASK-3 says. The ripgrep command in the example answered NUL-separated paths, exit 1 for no match, 2 with stderr for a missing folder. vsearch and query not run: there are no models and none were downloaded, so their time is unmeasured.

Checks: scripts/docs.sh passes.

## Review at close, 2026-10-09
A read-only reviewer who did not do the work said close, all three criteria met; it ran the decision's exact qmd command against the real qmd 2.8.3 and a ripgrep command and found every claim held. Its four gaps are settled in decision 11 by the lead: a timed-out or cut call is neither cached nor counted as healthy (only a call that finished in time is cached, and three calls that all missed the deadline start the rest); output decoding (os.fsdecode for paths) and a bound (4 times limit entries read, and the commands should limit themselves, since the SDK call has no output cap: a follow-up for the SDK); entries a failing exit code printed are still shown, above the problem row (ripgrep exit 2); item ids carry the providers and the rank, and the other rows have fixed ids. Also: the deadline floor is 0.5 s, realpath runs in each provider's thread, and decision 9's provider rule is scoped to feeds. Left for the owner: decision 11 is proposed; whether problem rows sit above or below the hits; the obsidian:// open example, which needs the Mac.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Decision 11 (proposed) defines the search plugin's provider interface (qmd and a generic command kind), its config schema with worked examples for qmd and a second provider, how providers sharing a keyword are searched in parallel, merged and ranked by their own order, what a failing, slow or missing provider shows, and what Enter and the other actions do. Closed on review; the qmd claims were checked against a real qmd.
<!-- SECTION:FINAL_SUMMARY:END -->
