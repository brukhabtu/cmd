---
id: DRAFT-1
title: 'Skill: GPUI 0.2 for cmd'
status: Draft
assignee:
  - '@brukhabtu'
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 04:37'
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
