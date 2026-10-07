---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

In a GPUI 0.2 view's key handler, `fn on_key(&mut self, event: &KeyDownEvent, ...)`, I need to tell Cmd-Backspace (clear the whole input) from plain Backspace, treat Return and Escape as commands, and for every other key without Cmd or Ctrl held get the text the key would type into the input. Which fields of the event do I read, and what are the exact key names gpui uses for Return and Escape? Give the Rust `match`.
