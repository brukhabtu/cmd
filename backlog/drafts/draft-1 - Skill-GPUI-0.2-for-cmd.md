---
id: DRAFT-1
title: 'Skill: GPUI 0.2 for cmd'
status: Draft
assignee:
  - '@brukhabtu'
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 05:41'
labels:
  - size-3
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Evidence from the foundation session
The model could not rely on its memory of GPUI: every API it used (Keystroke.key and key_char, WindowOptions fields, Context::listener, FocusHandle, Bounds::centered, FluentBuilder::when) had to be read from the vendored gpui-0.2.2 source, and on Linux the app crate cannot be compiled at all without a scratch workspace that patches xattr.

## Evidence from milestone 1
Two demonstrated misses, both caught by the scratch-workspace compile check, neither by memory: gpui re-exports smol::Timer only under a feature, so the app had to use cx.background_executor().timer(); and observe_window_activation lives on Context<V> and takes the Window, not on App. Also repeated lookup for cx.spawn's AsyncFnOnce(&mut AsyncApp) shape, WindowHandle::update, and primary_display().bounds(). Two pedantic clippy lints (unreadable_literal on colours, only_used_in_recursion) only surfaced in the rehearsal. This meets the bar for building the skill.

## What the skill would carry
Where the source lives in ~/.cargo/registry and how to read it; the verified API facts for 0.2.x listed above; the scratch-workspace recipe for compile-checking on Linux (vendored xattr patch, same workspace manifest without the profile override); the key names the platform layer emits; the executor timer instead of Timer.

## Eval cases it must pass (threshold 1.0, positive ablation delta)
1. 'Add a hover highlight to result rows' -> regex grader on crates/cmd-app/src/main.rs for .hover( and a cargo check that passes in the scratch workspace.
2. 'Redraw the view 500 ms after a query' -> regex for background_executor().timer and not for gpui::Timer.
3. 'Hide the window when it loses focus' -> regex for observe_window_activation taking a window argument.
4. 'Why does the window not take focus on open?' -> llm grader: the answer names FocusHandle and window.focus.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Review before milestone 2 (2026-10-07, after 1.14, 1.28 and 1.29 closed): the coming work is GPUI from end to end (1.10 text input, 1.12 window look, 1.24 icons, 1.27 active display, 1.30's Mac check), so the model will keep reading gpui-0.2.2 from the cargo registry and compile-checking in the Linux scratch workspace. Evidence added this session: none new on GPUI itself, since the window code only gained the start-trouble line; one pedantic clippy miss (needless_pass_by_value on a Vec parameter) cost a build cycle, which the check caught and a skill would not change. Verdict: build this skill first in milestone 2, before 1.10, with the four cases above and a fifth, 'compile-check cmd-app on Linux', graded by tool_used on the scratch recipe. The eval runs in CI only on a pull request touching .claude/plugins/cmd-dev (skills.yml), on the repository's Claude credential, so the build goes up as a pull request and the result is attached here before promotion.

Built as .claude/plugins/cmd-dev/skills/gpui-for-cmd/SKILL.md (commit follows): the verified gpui 0.2.2 facts as the window uses them, where the source is, the Linux scratch-workspace recipe, and the pedantic lints that bit. Eval cases next; the gate runs on the first pull request touching the plugin. Promotion waits on that result.

Five eval cases written under .claude/plugins/cmd-dev/evals/gpui-for-cmd-{timer,focus-loss,linux-check,keys,lints}: each run starts in an empty directory, so they are questions graded by regex on the answer (the executor timer and no Timer type; observe_window_activation taking the window and is_window_active; xattr, the crates-io patch and ENODATA; key_char, modifiers.platform and the key names; needless_pass_by_value and &[String]), with a Skill tool_used grader as the plugin-fired indicator that the two-arm run excludes from the score. Not run here: no credential in this container. Opening a pull request that touches the plugin runs the gate (threshold 1.0, with-without ablation, cost ceiling 15 USD, scripts/eval_gate.py on the delta); promote this draft only with that result attached.

Correction from the design review: gpui 0.2.2 re-exports smol::Timer unconditionally (src/gpui.rs:94) and 'use gpui::Timer' compiles in the scratch workspace, so the 'feature-gated Timer' miss recorded above does not hold; the evidence is the observe_window_activation miss, the Linux recipe, and the repeated lookups. The skill's Timer bullet is now the crate's convention, not a fact about gpui; the libc line names the version in the tree (0.2.190). Cases cut to three (focus-loss, linux-check, keys): the timer case rested on the false miss and the lints case would score the same without the skill; graders widened so a correct answer with the skill cannot fail on wording.
<!-- SECTION:NOTES:END -->
