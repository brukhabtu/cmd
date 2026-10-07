---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

In a GPUI 0.2 view's key handler, `fn on_key(&mut self, event: &KeyDownEvent, _window: &mut Window, cx: &mut Context<Self>)`, I need to tell Cmd-Backspace (clear the whole input) from plain Backspace, treat Enter and Escape as commands, and for every other key without Cmd or Ctrl held get the text the key would type into the input. Which fields of the event do I read, and what are the key names? Give the Rust `match`.
