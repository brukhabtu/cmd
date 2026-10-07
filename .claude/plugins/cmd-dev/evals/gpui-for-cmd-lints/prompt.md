---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [gpui]
---

This Cargo workspace lints with `clippy::pedantic` at `-D warnings`. I am adding this constructor to a GPUI view in it:

```rust
fn new(host: Host, trouble: Vec<String>, window: &mut Window, cx: &mut Context<Self>) -> Self {
    let mut state = Launcher::default();
    if !trouble.is_empty() {
        state.apply(Event::Noted(trouble.join("; ")));
    }
    Self { state, host, focus: cx.focus_handle(), shown: true }
}
```

`trouble` is only read. Which clippy lint will fail the build on it, and what is the fix? Name the lint and show the corrected signature.
