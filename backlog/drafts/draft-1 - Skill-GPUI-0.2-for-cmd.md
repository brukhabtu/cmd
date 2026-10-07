---
id: DRAFT-1
title: 'Skill: GPUI 0.2 for cmd'
status: Draft
assignee:
  - '@brukhabtu'
created_date: '2026-10-07 02:41'
labels:
  - size-3
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Evidence from the foundation session
The model could not rely on its memory of GPUI: every API it used (Keystroke.key and key_char, WindowOptions fields, Context::listener, FocusHandle, Bounds::centered, FluentBuilder::when) had to be read from the vendored gpui-0.2.2 source, and on Linux the app crate cannot be compiled at all without a scratch workspace that patches xattr. That is repeated lookup, not yet a demonstrated miss. Promote when a GPUI change lands wrong in review or CI.

## What the skill would carry
Where the source lives in ~/.cargo/registry and how to read it; the verified API facts for 0.2.x; the scratch-workspace recipe for compile-checking on Linux; the key names the platform layer emits.

## Eval cases it must pass (threshold 1.0, positive ablation delta)
1. "Add a hover highlight to result rows" -> regex grader on crates/cmd-app/src/main.rs for `.hover(` and a `cargo check` that passes in the scratch workspace.
2. "Make Cmd-1..9 run the nth result" -> regex for `keystroke.modifiers.platform` and for `Event::` handling in the view; tool_used Read on the gpui source.
3. "Why does the window not take focus on open?" -> llm grader: the answer names FocusHandle and window.focus.
<!-- SECTION:DESCRIPTION:END -->
