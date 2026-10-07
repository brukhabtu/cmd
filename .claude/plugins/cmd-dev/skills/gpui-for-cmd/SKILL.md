---
name: gpui-for-cmd
description: Use when editing crates/cmd-app or any Rust that touches gpui types, when answering how to do something in gpui 0.2, when compile-checking cmd-app on Linux, or when satisfying this workspace's pedantic clippy. Verified API facts for gpui 0.2.2 as this repository uses them, where to read its source, and the Linux check recipe.
---

# GPUI 0.2 for cmd

GPUI's API is not in memory in usable detail: in milestone 1 every API the window needed
was read from the gpui 0.2.2 source, and when one was recalled instead
(`observe_window_activation` placed on `App` rather than `Context<V>`) the build failed.
Everything below was read from that source and compiled in this repository, so answer
from these facts when the source is not on disk. Anything not listed here is read from the
source before it is used, never recalled.

## Where the source is

`~/.cargo/registry/src/*/gpui-0.2.2/src/` once the workspace has fetched its dependencies.
One grep finds a signature:

```sh
grep -rn "pub fn observe_window_activation" ~/.cargo/registry/src/*/gpui-0.2.2/src
```

## Facts verified in this repository, gpui 0.2.2

- **Keys.** `on_key_down(cx.listener(Self::on_key))` on the root element, with
  `.track_focus(&self.focus)`, delivers `&KeyDownEvent` whose `keystroke: Keystroke` has
  `modifiers` (`.platform` is Cmd on macOS, `.control` is Ctrl, `.alt` is Option,
  `.shift`), `key` (names such as `"backspace"`, `"left"`, `"right"`, `"up"`, `"down"`,
  `"enter"`, `"escape"`, or the character) and `key_char: Option<String>`.
- **Text goes through the input handler, not `key_char`.** Once a view installs an input
  handler, macOS routes keys like this (read from `platform/mac/window.rs`,
  `handle_key_event`): a key with a `key_char` reaches the key listeners first and, unless
  one calls `cx.stop_propagation()`, goes on to the input context, which inserts it through
  `replace_text_in_range`; a key without one (Backspace, the arrows, Escape, every Cmd
  chord) goes to the input context first and comes back to the listeners once. So the key
  listener must not insert `key_char` (every character would arrive twice) and must call
  `cx.stop_propagation()` on every key it takes. Text, dead keys and input-method
  composition arrive through `impl EntityInputHandler for View` (`replace_text_in_range`,
  `replace_and_mark_text_in_range`, `unmark_text`, `selected_text_range`,
  `text_for_range`, `bounds_for_range`, `character_index_for_point`, all in UTF-16
  offsets); the element installs it in `paint` with
  `window.handle_input(&focus, ElementInputHandler::new(bounds, view.clone()), cx)`. This
  repository's input is `crates/cmd-app/src/input.rs`.
- **Window activation.** `cx.observe_window_activation(window, |view, window, cx| ...)`
  lives on `Context<V>` and takes the `&mut Window`; inside, `window.is_window_active()`
  says which way it went. `App` has no such method.
- **Timers.** The convention here is `cx.background_executor().timer(duration).await`
  inside a spawned task, as `crates/cmd-app/src/main.rs` does; gpui also re-exports
  `smol::Timer`, which is not used in this crate.
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
- **Displays.** On macOS every display's `PlatformDisplay::bounds()` has origin `(0, 0)`:
  only the size is real, so the arrangement of displays and the pointer come from
  CoreGraphics (`crates/cmd-app/src/displays.rs`). `Window::bounds()` is relative to the
  window's own screen. `WindowOptions { display_id, window_bounds: Windowed(bounds) }`
  opens a window on that display with the origin relative to its top-left;
  `u32::from(DisplayId)` is the `CGDirectDisplayID`. Nothing moves an open window
  (the platform window has only `resize`), so changing display means `remove_window` then
  `open_window`.
- **Window look.** `WindowOptions.window_background: WindowBackgroundAppearance` (`Opaque`,
  `Transparent`, `Blurred`); on macOS `Blurred` makes the window non-opaque and puts an
  `NSVisualEffectView` under the content, so the root's background must be translucent
  (`rgba(0xRRGGBBAA)`). `window.appearance()` is `Light`, `VibrantLight`, `Dark` or
  `VibrantDark`; `cx.observe_window_appearance(window, |view, window, cx| ...)` on
  `Context<V>` fires when it changes. `rounded_lg`, `rounded_xl`, `rounded_2xl` are 8, 12
  and 16 px; `truncate()` is overflow hidden, no wrap, ellipsis.
- **Images and assets.** `gpui::Asset` has `type Source: Clone + Hash + Send`,
  `type Output: Clone + Send` and `fn load(source, cx: &mut App) -> impl Future`; `load`
  runs on the calling thread and its future on the background executor.
  `window.use_asset::<A>(&source, cx)` is `None` while loading and redraws the view when it
  arrives. `RenderImage::new(vec![image::Frame::new(buffer)])` takes BGRA frames;
  `img(Arc<RenderImage>)` is `Styled`, so `.size(px(..))` applies, and fits by `Contain`.
- **Elements.** `div()` with the fluent builders; `.when(condition, |this| ...)` needs
  `gpui::prelude::FluentBuilder`; `.children(iterator)`; colours as `rgb(0x1c_1c_1e)`.
- **Effects.** `cx.write_to_clipboard(ClipboardItem::new_string(text))`;
  `cx.open_url(&url)`; `cx.notify()` after any state change the view should redraw for.

## Compile-checking cmd-app on Linux

The workspace cannot build `cmd-app` on Linux: `xattr 0.2.3`, below gpui, uses
`libc::ENOATTR`, which the libc in this tree (0.2.190) defines for Apple and BSD targets
and not for Linux. CI builds the app on macOS. For clippy on Linux, use a scratch
workspace outside the repository:

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
`unreadable_literal` (colour literals need separators), `similar_names` (a `hint` beside a
`hit`), `redundant_closure`, `only_used_in_recursion`, `too_many_lines` (100 lines),
`match_wildcard_for_single_variants`, `cast_precision_loss` (a `usize as f32` in a const
assert needs an allow), and on 1.99 `chunks_exact(4)` with a constant wants
`as_chunks::<4>()`. Run the scratch clippy before pushing; CI's macOS job runs the same,
and it is the only lint of code under `cfg(target_os = "macos")` (see the objc2 and AppKit
skill).
