---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [appkit]
---

I want to call `NSApplication::sharedApplication` from macOS-only code in crates/cmd-app of the cmd repository, which needs a `MainThreadMarker`. Where does `MainThreadMarker` come from, and what has to be true of crates/cmd-app/Cargo.toml for the `use` line to compile on macOS?
