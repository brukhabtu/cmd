# Architecture

The model is LikeC4 in `docs/architecture/`, orthodox C4: a context view, a container view,
one component view, and one scenario. `npx likec4 start docs/architecture` opens it;
`npx likec4 validate docs/architecture` checks it.

## In one paragraph

cmd is one software system with two kinds of container. The **launcher app** is a Rust
process with a GPUI window. A **plugin process** is a Python program, one per installed
plugin, that the app starts and talks to over its stdin and stdout in newline-delimited
JSON. The app routes what the person types to the plugins that should see it, merges their
answers into one ranked list, and when the person presses Enter asks the owning plugin what
to do, then does it: copy, open, show, or hide. macOS is outside the system: the pasteboard,
Launch Services, and the global hotkey are reached through it.

## Why these shapes

**Plugins are processes, not embedded interpreters.** A plugin can crash, hang, print, or
depend on anything, and none of it reaches the window. The protocol is small enough to speak
from any language; Python is the first SDK, not the only possible one. The cost is a process
per plugin and a round trip per keystroke, which is why the protocol is one line each way
and the host keeps the processes alive. Decision 1 on the board has the alternatives.

**The core is pure.** `cmd-core` has no I/O. It knows the protocol's shapes, decides which
plugins see a query, merges answers, and runs the launcher's state machine: an event in, a
step out. `cmd-host` and `cmd-app` are the shell that performs the steps. The pure part is
where the tests are, and the shell is thin enough to read in one sitting.

**The plugin returns effects; the host performs them.** A plugin says "copy this" or "open
that" and the app does it. This keeps the plugin side simple and keeps the app in control of
the window, and it is the same idea as the core's steps, one level out.

**Crates are the components.** The component view of the app has three boxes because the
app has three crates. Cargo enforces that `cmd-core` depends on nothing of ours and that
`cmd-host` does not depend on the window.

## Where the boundaries are enforced

| Statement | Enforced by |
|---|---|
| The core does no I/O | `cmd-core` has no process, file, or GPUI dependencies in `Cargo.toml` |
| The SDK knows no plugin | Declared in `[tool.pypeeker.import-boundaries]`; not yet mechanical, because the rule cannot see across the two source roots. Board task "Make the SDK/plugin and core/shell import boundaries mechanical" |
| The Rust and Python protocols agree | `crates/cmd-host/tests/calculator.rs` drives the real plugin through uv |
| Plugins log to stderr, not stdout | The host rejects a non-protocol line and quotes it |

## Not yet

A global hotkey, hiding on focus loss, a real text input, plugin calls off the UI thread,
plugin restarts, icons, and an application bundle. Each is a task on the board under its
milestone.
