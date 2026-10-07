---
id: TASK-1.24
title: Icons in results
status: In Progress
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 07:27'
labels:
  - size-3
milestone: m-3
dependencies: []
parent_task_id: TASK-1
type: task
ordinal: 25000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Items may carry an icon (an app bundle path, a file path, or an SF Symbol name) and the view renders it
- [ ] #2 The protocol document, the Rust side and the Python side change together
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Protocol 1: one optional tagged icon on an item (path or symbol) in the three homes plus the adapter test; all four plugins and the SDK README move to 1; the window gets an icon slot in result_row resolved through GPUI's asset cache, with the AppKit path behind cfg(macos) and its pure helpers tested in the scratch workspace; macOS CI runs cargo test -p cmd-app as the proof of the AppKit path.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**What landed.** Protocol version 1: one optional field on an item, `icon`, tagged by `kind` like an effect, in two kinds, `{"kind": "path", "path": "/Applications/Safari.app"}` and `{"kind": "symbol", "name": "globe"}`. The three homes changed together: `crates/cmd-core/src/protocol.rs` (`VERSION` 1, `ACCEPTED` still `0..=1`, `enum Icon`, `Item.icon`), `python/cmd-sdk/src/cmd_sdk/protocol.py` (`PROTOCOL` 1, `PathIcon`, `SymbolIcon`, `Icon`, `Item.icon` as the last field so positional construction still works, exported from `cmd_sdk`), `docs/plugin-protocol.md` (title, every `protocol` number, a Versions paragraph, the Item section's icon table and rules). All four plugins carry icons: calculator `equal`, websearch `globe`, files a `PathIcon` of each file and `magnifyingglass` for the hint, system one symbol per command (`moon.zzz`, `lock`, `trash`, `circle.lefthalf.filled`) as a new `Command.symbol` field. The SDK README's websearch block and bullets follow. The window: `crates/cmd-app/src/icons.rs` is new, a `gpui::Asset` whose `load` asks AppKit on the main thread (`NSWorkspace::iconForFile` for a path, `NSImage::imageWithSystemSymbolName` with a symbol configuration for a symbol, then `TIFFRepresentation`, the bitmap page nearest 48 px, PNG out) and decodes the PNG in the background into GPUI's BGRA `RenderImage`, tinting a symbol with the palette's text colour; `result_row` in `main.rs` gained a 24 pt icon slot that is laid out only when some visible row has an icon and the cache key is the icon plus the tint, so a light or dark switch redraws symbols in the right colour. `cmd-app` depends on `image` (same major as GPUI's, png only) and, on macOS only, on `objc2-foundation` and `objc2-app-kit` feature sets; no new crate enters the lock. macOS CI and `scripts/check.sh`'s Darwin branch run `cargo test -p cmd-app` after clippy, and clippy there now covers `--all-targets`. `docs/architecture.md` no longer lists icons under Not yet.

**Where the code had moved past the plan.** The plan predates tasks 1.12, 1.20 and 1.21: the tint comes from the `Palette` that 1.12 introduced (no `TEXT` constant) and is part of the asset key from the start; the files and system plugins exist now and moved to version 1 in the same commit with icons of their own; `cargo test --workspace --exclude cmd-app` and the scratch workspace stayed the Linux recipe. `nearest` carries a `cfg_attr(not(macos), allow(dead_code))` because only the macOS resolver has several widths to choose from. The direct `objc2` dependency the plan listed is not needed: `downcast_ref` is an inherent `AnyObject` method reached through deref.

**Evidence (Linux).** `scripts/check.sh` green end to end: `cargo test --workspace --exclude cmd-app` (cmd-core 41 unit tests including `an_item_may_carry_a_path_or_a_symbol_icon` and `an_icon_of_an_unknown_kind_is_a_decode_error`; cmd-host: `an_item_s_icon_arrives_typed` through the fake plugin, the adapter tests asserting `Icon::Symbol("equal")` and `Icon::Symbol("globe")` through the real calculator and websearch processes, the doctor test seeing `"kind": "symbol"`), `uv run pytest -q` 129 passed (`test_icons_are_tagged_by_kind` both kinds, each plugin's icon asserted, the system wire test at protocol 1), ruff, mypy strict, pypeeker strict, import boundaries, index shape. In the scratch workspace: `cargo clippy -p cmd-app --all-targets -- -D warnings` exit 0 and `cargo test -p cmd-app` 7 passed (`nearest`, `tint_rgba`, `tint_of`, a 2x2 PNG to BGRA with and without tint, bad bytes to None, the cache key).

**Owed.** (1) The macOS CI run of `cargo test -p cmd-app`: the three `#[cfg(all(test, target_os = "macos"))]` tests in `icons.rs` (Calculator.app resolves to a PNG at least 48 px wide; `magnifyingglass` resolves to a glyph with an opaque pixel tinted `f2f2f7`; an unknown symbol and a missing path resolve to None) are the proof of the AppKit path, written against the objc2-app-kit 0.3.2 source, not run here. Budget a round trip or two: a wrong method name is a compile error there, and a headless runner may refuse `TIFFRepresentation` of a symbol image. (2) A person on a Mac: open the launcher, type `2+2` and `web rust`, see the equal and globe glyphs beside the rows; type `f readme` and see each file's own icon; type `sleep` and see the moon; point `CMD_PLUGINS` at a directory holding the fake plugin from `crates/cmd-host/tests/common/mod.rs` and query `icon` to see Safari's icon; record whether a list mixing rows with and without icons lines up, and whether the first batch of large app icons pauses visibly (TIFFRepresentation serialises every size up to 1024 px on the main thread, once per icon). (3) The symbol names `equal`, `globe`, `magnifyingglass`, `moon.zzz`, `lock`, `trash`, `circle.lefthalf.filled` are believed to be in the catalogue on current macOS; a missing one leaves its row without an icon rather than failing.

**gpui 0.2.2 facts used, for the gpui-for-cmd skill (not edited here).** `gpui::Asset` has `type Source: Clone + Hash + Send`, `type Output: Clone + Send` and `fn load(source, cx: &mut App) -> impl Future<Output = Output> + Send + 'static`; `App::fetch_asset` calls `load` on the calling thread and spawns the returned future on the background executor; `Window::use_asset::<A>(&source, cx) -> Option<A::Output>` returns `None` while loading and notifies the current view on the next frame when the load finishes. `RenderImage::new(vec![image::Frame::new(rgba)])` takes BGRA straight-alpha frames (gpui swaps channels 0 and 2 after decoding); `img(Arc<RenderImage>)` is an `Img` that implements `Styled`, so `.size(px(..))` applies, and its default `ObjectFit::Contain` scales a larger bitmap down. `Rgba` has public `r`, `g`, `b`, `a` in `0.0..=1.0`. Clippy 1.99 denies `chunks_exact(4)` with a constant in favour of `as_chunks::<4>()`.
<!-- SECTION:NOTES:END -->
