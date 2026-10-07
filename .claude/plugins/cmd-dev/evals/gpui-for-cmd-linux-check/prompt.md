---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

I am on Linux and this Rust workspace has a crate, cmd-app, that depends on gpui 0.2.2. `cargo clippy -p cmd-app` fails deep in the dependency tree before any of my code compiles, and CI builds the app on macOS. How do I get clippy to run on cmd-app on this Linux machine, as this repository does it? Name what fails and give the exact steps.
