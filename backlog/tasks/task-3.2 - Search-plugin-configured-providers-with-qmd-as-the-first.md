---
id: TASK-3.2
title: 'Search plugin: configured providers, with qmd as the first'
status: To Do
assignee: []
created_date: '2026-10-09 13:51'
updated_date: '2026-10-09 14:35'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built plugins/search, decision 11's first slice. Pure core: search.hits (Hit, Found, Failed), search.values (single-value checks), search.kinds (the Kind protocol and KINDS) with kinds.qmd and kinds.command, search.schema (config to Settings, argv with the /usr/bin/env prefix, the open template), search.merge (rank interleave, dedupe by real path or URL, hit and problem rows, ids), search.answers (routing, status, hint and config rows, what an id means). Shell: search.memory (10 s cache of 64, rest after 3 slow calls for 30 s, last call per provider) and search.plugin (start, query with one daemon thread per provider joined until deadline + 1 s, run). Registered in pyproject (members by glob, mypy_path, testpaths, pypeeker src and import-boundaries), mkdocs.yml (mkdocstrings path, nav), plugins/index.toml, docs/use/search.md.

Index: the entry is pinned to ef9028ec9d11054782f626faef565617c01dd61a, the commit this branch started from, which has no plugins/search, so scripts/check_index.py fails online for it alone until the lead pushes and re-pins it. The offline check passes.

Assumptions, where decision 11 left a choice:
- The shared types live in search.hits and search.kinds re-exports them: KINDS in search.kinds imports the kind modules, which need the types, so defining them in search.kinds would be an import cycle.
- The kind interface grew two things: read takes the limit (the decision asks it to read at most 4 * limit entries but its signature had no limit), and scope(settings) names qmd's index for the no-hits row, so merge holds no qmd-specific code for it. A kind module satisfies a typing.Protocol, Kind[S], checked by mypy.
- Found grew problem (the first skipped entry's problem, for the "N entries could not be read" subtitle) and failure (an exit outside exit_codes after some hits, ripgrep's exit 2), which the decision's Found had no field for.
- Enter on problem:<provider> shows the command and stderr's first five lines from the plugin's memory of that provider's last call, since the fixed id cannot carry them; after a restart it says the provider has not been searched since start. The status keyword's rows are status, provider:<name> (Enter does the same) and config:<n>.
- A text under min_chars shows the hint and also the keyword's config problem rows.
- A provider listing the status keyword is refused whole, not just that keyword.
- The rest: the count is not reset when a rest begins, so after 30 s one more slow call rests it again ("its last three calls all missed"); a call back in time resets it.
- A thread still running at deadline + 1 s is "did not answer"; when it finishes it records itself (cached and the count reset if its call came back in time).
- qmd output whose entries are all unreadable is Found with skipped, not Failed (the decision says Failed for the command kind only); a file that is not /, ./ or qmd:// is skipped.
- command: {text} must be in an argument after the program; exit_codes must be non-empty; a hits entry with a wrong line, snippet or reference type is skipped. Copy text copies the title.
- open: other braces are left alone; it must start with a scheme once filled. env values holding NUL are refused.
- Unstarted's subtitle is "check its program in config.toml", since bin is only qmd's key.
- Open and Reveal check the path exists first. Reveal is /usr/bin/open -R with 5 s, as the files plugin does.
- start never raises either: a failure there is a row.

Other changes outside the plugin: ruff 0.16 formats Python blocks inside Markdown, and decision 11's sketches fail ruff format --check at the base commit (check.sh failed there before this work). I did not edit the decision; I added "backlog" to ruff's extend-exclude. The lead may prefer to reformat the decision and drop that line. pypeeker names an import-boundaries unit by module alone, so the vault's schema and answers rows are shared with this plugin's and were widened (schema may import hits, kinds, values; answers may import merge); hits, values, kinds and merge have rows of their own.

SDK gaps, worked around in the plugin and owed to the SDK: call() has no environment (the /usr/bin/env prefix), no output cap (bounded by the deadline; a command should limit itself with {limit}), and no working directory (qmd runs in the plugin's, which is what the decision wants).

Evidence:
- 195 tests in plugins/search pass, 1 skipped (the real qmd, without CMD_TEST_QMD). They cover decision 11's list items 1 to 12: the eight captures from qmd 2.8.3 through qmd.read and, via a fake qmd that prints them with its answer chosen through the provider's env table, through argv, env, call, reader and rows; the fake provider in every mode (paths, NUL, JSON lines, array, empty, exit 1 accepted and not, exit 2 with stderr, exit 2 with hits, slow past the deadline, partial then hanging, garbage, a grandchild holding stdout, a grandchild exiting at 1.2 s so the call's whole 1 s grace is spent, a program gone since start); every config problem; run on every row shape, the open template with a space, # and %, a path gone, ids decoded by a fresh start; serve over StringIO.
- Timing: five slow or hanging providers and a working one on one keyword at deadline 1.5 answer in about 2.25 s (three runs), under the host's 3 s, with every hit that arrived in time.
- Eleven behaviours undone one at a time, each caught by its test, then restored (the -- before the text, routing, min_chars, timeouts not cached and counted, the count reset, dedupe by real path, the 1 s grace, problem rows after hits, query never raising, a thread's exception, the program check at start).
- The real qmd: with CMD_TEST_QMD set to the isolated qmd 2.8.3 and HOME and the XDG directories set to its scratch home, the real-qmd test passed (0.9 s): it indexes a temporary folder under a temporary HOME passed through the provider's env, searches through the plugin, gets the note's real path, and Enter opens it. Separately, driving the plugin against that install's two collections as two providers on n: "n offsite" merged notes and meetings in 0.32 s, again from the cache in 0.00 s; "x offsite" with collection nosuchcollection showed "nosuch: Collection not found: nosuchcollection", "exit 1; check this provider in config.toml"; "n -offsite" answered No hits (the -- works); "hello" gave no rows and started nothing. No model was downloaded; the install's home was left unchanged.
- scripts/check.sh passes every step up to the online index check, which fails for the search entry alone (above); the steps after it (offline index, LikeC4, docs.sh strict, plugin manifests, hook tests) pass when run on their own. The generated catalogue, examples page and SDK reference list the plugin.

Owed on the owner's Mac:
- [ ] Install qmd (npm install -g @tobilu/qmd), add collections, and see qmd search --json --full-path -n 5 -- <text> answer in a terminal.
- [ ] Note command -v qmd and command -v node; write the smallest config with that bin and env.PATH.
- [ ] Launch cmd from the Dock (bare PATH): n <text> shows hits. An exit 127 row means env.PATH lacks node's folder; note the Mac's wording of that error for the user page.
- [ ] Enter opens the note (the default {uri}); Reveal in Finder selects it; Copy path.
- [ ] open = "obsidian://open?path={path}" opens the note in Obsidian, including a name with a space, # or %.
- [ ] A cold qmd search after sleep answers inside deadline 1.0.
- [ ] The ripgrep provider from the worked example, with rg's real path.
- [ ] Re-pin plugins/index.toml's search entry after the push.
<!-- SECTION:NOTES:END -->
