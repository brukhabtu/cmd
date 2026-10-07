---
id: decision-5
title: >-
  The global hotkey comes from Carbon through the global-hotkey crate,
  Option-Space by default
date: '2026-10-07 03:39'
status: proposed
---
## Context

A launcher has to appear from any application on a key chord. macOS offers three ways in:
the Carbon `RegisterEventHotKey` API, a `CGEventTap`, and an `NSEvent` global monitor.
The spike (task 1.7) read the sources of the `global-hotkey` crate (0.8.0, the tauri-apps
project) and of GPUI 0.2.2 to decide which fits a GPUI app.

## Decision

Use the `global-hotkey` crate, whose macOS backend calls `RegisterEventHotKey` and installs
a Carbon event handler on the application event target.

- **Permissions:** none. A registered hot key needs neither Accessibility nor Input
  Monitoring. A `CGEventTap` and an `NSEvent` global monitor both need Accessibility, which
  is a System Settings trip on first launch and a support burden after every update.
- **Delivery:** the Carbon handler runs on the main thread when the NSApplication run loop
  processes events, which GPUI's `Application::run` drives. The crate hands each event to a
  `Send + Sync` callback. That callback cannot hold GPUI's `AsyncApp`, so it pushes onto an
  `async-channel` and a foreground task spawned with `cx.spawn` awaits the channel and
  shows the window. Showing is `cx.activate(true)` to unhide the application, then
  `window.activate_window()` and focusing the input.
- **Hiding:** `cx.hide()` hides the application, which is what Spotlight-style launchers
  do. A per-window hide is not in GPUI's platform window trait, and is not needed.
- **Default chord: Option-Space.** Spotlight holds Cmd-Space as a system shortcut and
  wins any contest for it. Taking Cmd-Space is the person's choice: they switch off
  Spotlight's shortcut in System Settings and set `CMD_HOTKEY=super+Space`. The crate's
  chord syntax is `alt`, `super`, `ctrl`, `shift` joined with `+` and a `Code` name such as
  `Space`. This answers half of the intent's first open question: the launcher sits beside
  Spotlight until the person decides otherwise.
- **The demo is the app.** `cmd-app` itself registers the chord and shows and hides on it
  (task 1.9). macOS CI compiles it; the crate also compiles on Linux (X11 backend), so the
  scratch-workspace compile check still works. Pressing the key on a Mac is the one step
  this environment cannot take.

## Consequences

- One more crate in `cmd-app`, with `objc2` behind it on macOS. The X11 backend compiles
  on Linux and does nothing useful there, which is fine: Linux is not a target.
- A chord that is already taken fails at registration with an error naming the chord; the
  app reports it on stderr and runs without a hotkey rather than refusing to start.
- Changing the chord at runtime (settings) means unregister and register, both supported.
- If a future feature needs to see keys the app does not own (a double-tap of Option, say),
  that is an event tap and the Accessibility prompt that comes with it; a separate decision.
