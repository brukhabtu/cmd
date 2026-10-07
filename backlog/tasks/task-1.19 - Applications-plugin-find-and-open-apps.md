---
id: TASK-1.19
title: 'Applications plugin: find and open apps'
status: Done
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 11:18'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 20000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Scans /Applications, ~/Applications and /System/Applications; fuzzy-matches names with a score in 0..1
- [x] #2 Enter opens the app through Launch Services; the definite calculator answer still ranks above fuzzy app matches
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
A Python plugin in the shape of the calculator: plugins/applications with scan.py (bundles under the three roots, two levels deep, pure apart from reading directories), matching.py (a pure fuzzy scorer in (0, 1], exact 1.0) and __init__.py (query, run with a file URL open effect, --root for tests), unit tests on tmp_path trees; a core fix in cmd-core's merge so a 1.0 fuzzy score sits below a definite answer; an adapter test in cmd-host driving the real plugin through uv at a fake root beside the real calculator and proving the merge puts the calculator's answer first; pyproject, uv.lock, plugins/index.toml, docs/plugin-protocol.md and README follow.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed (branch worktree-wf_1af770a2-fcd-2, finished after a usage-limit cut; the partial work was kept and fast-forwarded onto ccr-16512bde-x72oqp at 6b3f8e6 with no conflict):
- plugins/applications: scan.py finds .app bundles two levels under /Applications, ~/Applications and /System/Applications, never descending into a bundle, skipping a missing root; matching.py scores a subsequence match in (0, 0.95] and an exact name 1.0; __init__.py answers up to 8 rows with icon = PathIcon of the bundle, and Enter returns Open with the bundle's file:// URL (Path.as_uri()); --root DIR replaces the defaults for tests.
- cmd-core merge: an item with no score now ranks above every scored item, even one scored 1.0; before, a 1.0 tie went to plugin order and the applications plugin (first by name) won over the calculator.
- crates/cmd-host/tests/applications.rs: the real plugin through uv at a fake root beside the real calculator; answers_to collects both plugins' answers to one query, since answer_from drops the other plugin's answer (the first draft of this test hung on exactly that).
- docs/plugin-protocol.md: an open target for a file or app is a file:// URL. README names the plugin. pyproject (mypy_path, pytest testpaths, pypeeker src and the scan/matching units), uv.lock.
- plugins/index.toml: applications entry with ref 6b3f8e686b578e4f07e37f169fcee752bc8d4d9c, the head of ccr-16512bde-x72oqp before this merge, which does not hold the plugin. It MUST be re-pinned to the merge commit once the branch is merged and pushed; until then check_index.py with the network fails on this entry, and without the entry test_the_repository_index_lists_every_plugin_here fails.

Evidence: uv run pytest -q plugins/applications/tests 82 passed. cargo test -p cmd-core query 11 passed; with the old merge restored a_perfect_fuzzy_score_still_sits_below_a_definite_answer fails (left ["1+1 app", "2"]) and so does the adapter test (left ["1+1", "2"]). cargo test -p cmd-host --test applications --test calculator 1 + 2 passed. scripts/check.sh: red at the online index step only (the pin above); every other step green; run on the script's offline path (github.com redirected for ls-remote) it prints all checks passed.

Owed on a Mac: cargo run -p cmd-app, type saf, Enter: Safari opens through Launch Services (NSWorkspace on file:///Applications/Safari.app) and the window hides; an already-running app comes to the front; term finds /System/Applications/Utilities/Terminal.app; rows show the bundle icons; no ~/Applications gives no error; the per-keystroke scan of the real roots stays well under the 3 s query timeout.

Closed on the reviewer's verdict (CLOSE) against worktree commit dea462f, merged as part of f4b3155; the index entry is re-pinned to that merge, which check_index.py now reads from GitHub. Owed on a Mac: type part of an app's name and see it ranked first, Enter launches it through the file URL, an app two levels down under /Applications is found, and the per-keystroke scan stays in the milliseconds.
<!-- SECTION:NOTES:END -->
