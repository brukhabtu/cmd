# Working on the core

The core is Rust, in three crates, and the plugins around it are Python.

| Where | What |
|---|---|
| `crates/cmd-core` | The functional core: state, routing, the protocol's types. No I/O. |
| `crates/cmd-host` | The imperative shell around plugins: processes, workers, install. |
| `crates/cmd-app` | The GPUI window, the hotkey, and the macOS integration. |
| `python/cmd-sdk` | The plugin SDK. |
| `plugins/` | The plugins that ship with cmd, one directory each. |

- [Setting up](setup.md) to build, test and check, on macOS or Linux.
- [Architecture](../architecture.md): why the pieces are shaped the way they are.
- [The crates](crates.md) and the [Rust API](rust-api.md), generated from the code.
- [How work moves](process.md) from an idea on the board to a closed task.
- [Decisions](decisions/index.md): the choices that shaped it, and why.
