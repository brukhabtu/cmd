---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

I am working on cmd, a macOS launcher whose window is a GPUI 0.2 view (`impl Render for LauncherView`, methods take `cx: &mut Context<Self>`). After the view sends a query to the plugins it should redraw itself once, 500 ms later, without blocking anything, so a "waiting on" line can appear. Give me the Rust for that, as it would go inside a method of the view, and name the exact gpui APIs it uses.
