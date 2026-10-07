# cmd

A launcher for macOS in the place of Spotlight, in the spirit of Raycast: press the hotkey,
type, see results, press Enter. The core is Rust on [GPUI](https://www.gpui.rs); plugins are
Python, so anyone can extend it without touching the Rust.

Status: milestone 0, foundation. The pieces exist and talk to each other; there is no
hotkey, no app launcher plugin, and no bundle yet. The board in `backlog/` has the plan.

## Layout

| Path | What |
|---|---|
| `crates/cmd-core` | The logic. Protocol types, query routing, result merging, the launcher state machine. No I/O. |
| `crates/cmd-host` | Finds plugins, runs each as a process, speaks the protocol over stdin and stdout. |
| `crates/cmd-app` | The window. GPUI, keys in, steps out. |
| `python/cmd-sdk` | Write a plugin in Python: the types and `serve()`. |
| `plugins/` | Plugins. `calculator` is the first. |
| `docs/` | `architecture.md` (C4, in LikeC4), `plugin-protocol.md`, `skills.md`. |
| `backlog/` | The board: intent, milestones, tasks, decisions. |
| `.claude/` | Claude Code settings and plugins, including how this repository is worked on. |

## Build and run

Rust 1.90 or later and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-packages --all-groups     # Python 3.15 and the plugins' environments
cargo run -p cmd-app                    # macOS: opens the launcher, loads ./plugins
```

Type `2 + 2 * 3`, press Enter, and `8` is on the clipboard.

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

## Working on cmd with Claude Code

`.claude/settings.json` enables two vendored plugins: `philosophy` (how the work is done)
and `cmd-dev` (skills for this repository, each gated by an eval). `CLAUDE.md` is the map.
