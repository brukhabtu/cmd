---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

In a GPUI 0.2 app (the cmd launcher), the window must hide itself when it loses focus, the way Spotlight does. From the view's constructor, how do I subscribe to the window becoming active or inactive, and how do I tell inside the callback which way it went? Give the exact method, which type it is on, what it takes, and the Rust call with its closure signature.
