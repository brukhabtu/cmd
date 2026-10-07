---
name: objc2-appkit-for-cmd
description: Use when writing or changing Rust under cfg(target_os = "macos") in crates/cmd-app, calling AppKit, Foundation or CoreGraphics through objc2, objc2-foundation, objc2-app-kit or core-graphics, or when asked how such code is checked from Linux. The objc2 0.6 facts this repository has paid for, the dependency entries, and the rule that only CI's macOS job compiles this code.
---

# objc2 and AppKit from Rust in cmd

Code under `cfg(target_os = "macos")` is never compiled, linted or tested on Linux, so
every mistake in it surfaces only in CI's macOS job, one push and a few minutes later. In
milestone 2 that cost three CI round trips: an owned value borrowed by `downcast_ref`, a
type named from a crate the app did not depend on, and Apple type names unquoted in a doc
comment. The facts below are verified by code that now passes that job; answer from them
when the source is not on disk.

## How such code is checked

- Only `.github/workflows/ci.yml`'s macOS job (`macos-latest`, arm64) compiles it, with
  `cargo clippy -p cmd-app --all-targets -- -D warnings`, and runs its tests with
  `cargo test -p cmd-app`. Neither the Linux scratch workspace nor `scripts/check.sh` sees
  it.
- So push macOS-only code in a small commit of its own, read that job's result
  (`list_workflow_jobs` then `get_job_logs` on the failed job), and stack nothing on it
  until it is green.
- Keep the logic that can be pure in cfg-neutral helpers with tests (as
  `crates/cmd-app/src/icons.rs` and `displays.rs` do), so Linux checks the part it can.
- Pedantic clippy runs there too: in doc comments, quote Apple names in backticks
  (`` `NSPanel` ``, `` `LSUIElement` ``, `` `PopUp` ``), or `doc_markdown` fails the job.

## Dependencies

`crates/cmd-app/Cargo.toml` has one `[target.'cfg(target_os = "macos")'.dependencies]`
table: `objc2 = "0.6"`, `objc2-foundation` and `objc2-app-kit` 0.3 with
`default-features = false` and an explicit feature per class used (`NSArray`, `NSData`,
`NSDictionary`, `NSEnumerator`, `NSString`; `NSApplication`, `NSBitmapImageRep`,
`NSFontDescriptor`, `NSImage`, `NSImageRep`, `NSResponder`, `NSRunningApplication`,
`NSWorkspace`), and `core-graphics = "0.24"`. A class missing its feature is a compile
error on macOS only. Add a feature to the existing entry; never add a second entry for the
same crate. A crate that is only a transitive dependency cannot be named in `use`.

## objc2 facts, as this repository uses them

- `NSArray::iter()` yields owned `Retained<T>`, not references. Downcast an element with
  `Retained::downcast::<U>()`, which consumes it and returns
  `Result<Retained<U>, Retained<T>>`; `downcast_ref` borrows the element and cannot outlive
  the closure. Collect into `Vec<_>` and let the type be inferred.
- `MainThreadMarker::new()` is an `Option`; AppKit calls that need the main thread take the
  marker, as in `NSApplication::sharedApplication(mtm)`.
- `setActivationPolicy(NSApplicationActivationPolicy::Accessory)` returns whether AppKit
  accepted it; GPUI sets the regular policy as it finishes launching, so the accessory
  policy is set first thing in the `run` closure.
- Reading an AppKit constant such as `NSFontWeightRegular` is `unsafe`; so is a method
  that takes an untyped dictionary, such as `representationUsingType_properties`. Each
  `unsafe` block carries a `SAFETY` comment.
- Methods that can return nil return `Option<Retained<T>>`:
  `NSImage::imageWithSystemSymbolName_accessibilityDescription`,
  `imageWithSymbolConfiguration`, `TIFFRepresentation`, `representationUsingType_properties`.
- Strings go in as `&NSString::from_str(text)`; data comes out with `to_vec()`.

## CoreGraphics

The arrangement of displays comes from `CGDisplay::new(id).bounds()` and the pointer from a
null event's location, `CGEventSource::new(CGEventSourceStateID::HIDSystemState)` then
`CGEvent::new(source)` and `.location()`: one global space, no Accessibility permission.
GPUI's own display bounds all start at the origin, so they cannot place a window.
