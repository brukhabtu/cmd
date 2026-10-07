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
plugins see a query, merges answers as they arrive, and runs the launcher's state machine:
an event in, a step out. `cmd-host` and `cmd-app` are the shell that performs the steps.
The pure part is where the tests are, and the shell is thin enough to read in one sitting.

**The window never waits on a plugin.** Each plugin has a worker thread in `cmd-host` that
owns its process. A query goes to the workers as a command and returns at once; answers
come back as events on a channel the window's executor awaits, each tagged with the
generation of the text it answers, so a late answer to an older query is dropped and a
slow plugin delays only its own rows. Nor does it wait at start-up: the plugins are found
on the main thread, the window opens, and only then are they started on a thread beside
it, each reported as it comes up, so a first launch says which plugins it is still
waiting on. A plugin whose process dies or hangs is started
again with back-off, a plugin whose files change is started again on the new code, and
the window says so each time. `cmd plugin doctor` runs the same process layer from the
command line for plugin authors, and `cmd plugin install`, `update`, `remove` and `list`
are the same crate, answered by the app binary before any window exists.

**The plugin returns effects; the host performs them.** A plugin says "copy this" or "open
that" and the app does it. This keeps the plugin side simple and keeps the app in control of
the window, and it is the same idea as the core's steps, one level out.

**Crates are the components.** The component view of the app has three boxes because the
app has three crates. Each crate's `Cargo.toml` declares what it may depend on, so a new
dependency from the core on the host, or from the host on the window, is a visible change
to a manifest rather than a quiet import.

## Where the boundaries are enforced

| Statement | Enforced by |
|---|---|
| The core does no I/O | `crates/cmd-core/clippy.toml` disallows `std::process`, `std::fs`, `std::net`, stdin and `std::env::var`; clippy runs with warnings as errors |
| The core does not know the host or the window | `cmd-core` depends on nothing of ours in its `Cargo.toml`; a cycle would not build |
| The SDK's protocol module never imports its shell | `[tool.pypeeker.import-boundaries]` in `pyproject.toml`: `protocol` may import nothing of ours, `serve` may import `protocol`; `pypeeker check --strict` in `scripts/check.sh` |
| The SDK knows no plugin, and no plugin knows another | `scripts/import_boundaries.py` reads every absolute import under the source roots and fails on `cmd_sdk` importing a plugin package or a plugin importing a sibling; `scripts/check.sh` runs it |
| The Rust and Python protocols agree | `crates/cmd-host/tests/calculator.rs` drives the real plugin through uv |
| Plugins log to stderr, not stdout | The host rejects a non-protocol line and quotes it |
| The model matches the syntax LikeC4 accepts | `npx likec4 validate` in `scripts/check.sh`; the C4 discipline itself (one level per view, titled edges) is reviewed, not linted, in this repository |

## Not yet

A global hotkey, hiding on focus loss, a real text input, plugin calls off the UI thread,
and plugin restarts. Each is a task on the board under its milestone.

The application bundle exists: `scripts/bundle.sh` builds `cmd.app` and the macOS CI job
publishes it. By decision 7 it carries `uv` in `Contents/MacOS` beside the binary and
nothing else; the plugins' Python is fetched by that uv on first launch once the runtime
wiring lands (its own task), and until then plugins resolve uv from the inherited PATH.
