---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

The cmd launcher's query line is a GPUI 0.2 view on macOS. Typing should work for plain keys, for dead keys like Option-E then E, and for Japanese input-method composition. Where should the typed text reach the view, and what must the view's key-down handler do and not do so that no character arrives twice? Name the gpui trait and methods involved.
