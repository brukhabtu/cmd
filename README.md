# cmd

A launcher for macOS in the place of Spotlight, in the spirit of Raycast: press the hotkey,
type, see results, press Enter. The core is Rust on [GPUI](https://www.gpui.rs); plugins are
Python, so anyone can extend it without touching the Rust.

Status: milestone 0, foundation. The pieces exist and talk to each other; there is no app
launcher plugin yet. CI builds `cmd.app` on every push and publishes it as an artifact;
`scripts/bundle.sh` builds the same bundle on a Mac. The board in `backlog/` has the plan.

## Layout

| Path | What |
|---|---|
| `crates/cmd-core` | The logic. Protocol types, query routing, result merging, the launcher state machine. No I/O. |
| `crates/cmd-host` | Finds plugins, runs each as a process, speaks the protocol over stdin and stdout. |
| `crates/cmd-app` | The window. GPUI, keys in, steps out. |
| `python/cmd-sdk` | Write a plugin in Python: the types and `serve()`. |
| `plugins/` | Plugins: `calculator`, `websearch` and `system` (sleep, lock, empty Trash, dark mode). |
| `docs/` | `architecture.md` (C4, in LikeC4), `plugin-protocol.md`, `skills.md`. |
| `backlog/` | The board: intent, milestones, tasks, decisions. |
| `.claude/` | Claude Code settings and plugins, including how this repository is worked on. |

## Build and run

Rust 1.99, which `rust-toolchain.toml` pins, and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-packages --all-groups     # Python 3.15 and the plugins' environments
cargo run -p cmd-app                    # macOS: opens the launcher, loads ./plugins
```

Press Option-Space anywhere to bring it up, type `2 + 2 * 3`, press Enter, and `8` is on the
clipboard. Escape or a click elsewhere hides it. To use Cmd-Space instead, switch off
Spotlight's shortcut in System Settings and run with `CMD_HOTKEY=super+Space`.

To try the bundle, download the `cmd.app` artifact from a CI run, unzip it, and since it is
not yet signed (task 1.25), clear the quarantine before opening it:

```sh
unzip cmd.app.zip && xattr -dr com.apple.quarantine cmd.app && open cmd.app
```

It shows no Dock icon; Option-Space brings the window up. It carries `uv` beside the
binary and no plugins: install them with `cmd.app/Contents/MacOS/cmd plugin install <name>`.

On Linux the app crate does not compile (an `xattr`/`libc` clash below GPUI, not ours), so
run the rest: `cargo test --workspace --exclude cmd-app`.

## Checks

```sh
scripts/check.sh
```

Runs what CI runs: Rust formatting, clippy and tests, including the adapter test that drives
the real calculator plugin through uv; ruff, mypy and pytest for Python; validation of the
Claude Code plugins.

## Writing a plugin

Read `docs/plugin-protocol.md` and `python/cmd-sdk/README.md`, then copy
`plugins/calculator`. A plugin is a directory with a `cmd-plugin.toml`, a `Description`, a
`query` function and a `run` function.

Installed plugins live in `~/Library/Application Support/cmd/plugins`, one directory each.
`cmd plugin install <name | owner/name | url | path>`, `update`, `remove` and `list` manage
them from the app's own binary (`cargo run -p cmd-app -- plugin list` from a clone), and
`cmd plugin doctor <dir>` runs one directory the way the launcher does. The names come
from `plugins/index.toml`. The app also loads `./plugins` from the directory it was started
in, which is how this repository's plugins run during development.
`CMD_PLUGINS=/dir:/other` replaces both.

## Working on cmd with Claude Code

`.claude/settings.json` enables two vendored plugins: `philosophy` (how the work is done)
and `cmd-dev` (skills for this repository, each gated by an eval). `CLAUDE.md` is the map.
