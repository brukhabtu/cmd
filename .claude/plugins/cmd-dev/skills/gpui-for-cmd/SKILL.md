---
name: gpui-for-cmd
description: Use when editing crates/cmd-app or any Rust that touches gpui types. Verified API facts for gpui 0.2.2 as this repository uses them, where to read its source, the recipe that compile-checks cmd-app on Linux (the workspace itself cannot build it there), and the pedantic clippy lints that bite.
---

# GPUI 0.2 for cmd

GPUI's API is not in memory in usable detail: in milestone 1 every API the window needed
was read from the gpui 0.2.2 source, and the two times it was recalled instead (a
feature-gated `Timer` re-export, `observe_window_activation` placed on the wrong type) the
build failed. Everything below was read from that source and compiled in this repository.
Anything not listed is read from the source before it is used, never recalled.

## Where the source is

`~/.cargo/registry/src/*/gpui-0.2.2/src/` once the workspace has fetched its dependencies.
One grep finds a signature:

```sh
grep -rn "pub fn observe_window_activation" ~/.cargo/registry/src/*/gpui-0.2.2/src
```

## Facts verified in this repository, gpui 0.2.2

- **Keys.** `on_key_down(cx.listener(Self::on_key))` on the root element, with
  `.track_focus(&self.focus)`, delivers `&KeyDownEvent` whose `keystroke: Keystroke` has
  `modifiers` (`.platform` is Cmd on macOS, `.control` is Ctrl), `key` (names such as
  `"backspace"`, `"up"`, `"down"`, `"enter"`, `"escape"`, or the character) and
  `key_char: Option<String>`, the text the key would insert.
- **Window activation.** `cx.observe_window_activation(window, |view, window, cx| ...)`
  lives on `Context<V>` and takes the `&mut Window`; inside, `window.is_window_active()`
  says which way it went. `App` has no such method.
- **Timers.** gpui re-exports `smol::Timer` only behind a feature. Use
  `cx.background_executor().timer(duration).await` inside a spawned task.
- **Tasks.** On `Context<V>`: `cx.spawn(async move |view, cx| { ... })` where `view` is a
  `WeakEntity<V>` and `view.update(cx, |view, cx| ...)` returns a `Result` because the
  entity may be gone. On `App`: `cx.spawn(async move |cx: &mut AsyncApp| ...)`. A
  `WindowHandle<V>` is updated with `window.update(cx, |view, window, cx| ...)`, also a
  `Result`. Call `.detach()` on a task that is not awaited.
- **Focus.** `cx.focus_handle()` makes a `FocusHandle`; `window.focus(&handle)` focuses it.
- **Showing and hiding the app.** `cx.activate(true)` brings the app forward,
  `window.activate_window()` the window; `cx.hide()` hides the app. Losing focus arrives
  through the activation observer above.
- **Opening a window.** `WindowOptions { window_bounds: Some(WindowBounds::Windowed(bounds)),
  titlebar: None, kind: WindowKind::PopUp, is_movable: false, is_resizable: false,
  is_minimizable: false, ..Default::default() }`, then
  `cx.open_window(options, |window, cx| cx.new(|cx| View::new(..., window, cx)))`, which
  returns a `Result<WindowHandle<V>>`.
- **Displays.** `cx.primary_display()` is an `Option` of a display with `.bounds()`;
  `Bounds::centered(None, size, cx)` centres on the primary display.
- **Elements.** `div()` with the fluent builders; `.when(condition, |this| ...)` needs
  `gpui::prelude::FluentBuilder`; `.children(iterator)`; colours as `rgb(0x1c_1c_1e)`.
- **Effects.** `cx.write_to_clipboard(ClipboardItem::new_string(text))`;
  `cx.open_url(&url)`; `cx.notify()` after any state change the view should redraw for.

## Compile-checking cmd-app on Linux

The workspace cannot build `cmd-app` on Linux: `xattr 0.2.3`, below gpui, uses
`libc::ENOATTR`, which libc 0.2.182 and later do not define, and rustix pins the newer
libc. CI builds the app on macOS. For clippy on Linux, use a scratch workspace outside the
repository:

1. Copy `Cargo.toml` and `rust-toolchain.toml` there; in the copied `Cargo.toml` drop the
   `[profile.dev.package."*"]` section and append
   `[patch.crates-io]` with `xattr = { path = "vendor/xattr" }`.
2. Copy `~/.cargo/registry/src/*/xattr-0.2.3` to `vendor/xattr` there and, in its
   `src/sys/mod.rs`, define `pub const ENOATTR: ::libc::c_int = ::libc::ENODATA;` for Linux.
3. On every check: `rm -rf $S/crates && cp -r crates $S/crates && (cd $S && cargo clippy
   -p cmd-app --all-targets -- -D warnings)`. The first build takes minutes, later ones
   seconds.

The scratch workspace and the patch are never committed; `cargo test --workspace
--exclude cmd-app` is what runs in the repository on Linux.

## Pedantic clippy

The workspace lints with `clippy::pedantic` at `-D warnings`, and these bit in this crate:
`needless_pass_by_value` (take `&[T]` or `&str` unless the value is consumed),
`unreadable_literal` (colour literals need separators), `similar_names`,
`redundant_closure`, `only_used_in_recursion`, `too_many_lines` (100 lines),
`match_wildcard_for_single_variants`. Run the scratch clippy before pushing; CI's macOS
job runs the same.
