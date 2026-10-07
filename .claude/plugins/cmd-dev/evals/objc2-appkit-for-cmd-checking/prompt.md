---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [appkit]
---

I am on Linux and changed Rust code under `#[cfg(target_os = "macos")]` in the cmd repository's crates/cmd-app. How do I know it compiles and passes clippy before anything else is built on top of it?
