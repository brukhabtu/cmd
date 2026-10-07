---
id: decision-1
title: Plugins are Python processes speaking JSON lines over stdin and stdout
date: '2026-10-07 02:41'
status: proposed
---
## Context

The launcher must be extensible by people who will not write Rust. The options were: embed Python in the process (PyO3), load plugins as WebAssembly, speak MCP to plugin servers, or run each plugin as a child process speaking a small line protocol.

## Decision

Each plugin is a process the app starts from its `cmd-plugin.toml`, speaking newline-delimited JSON over stdin and stdout: `describe`, `query`, `run`. The plugin returns effects (close, copy, open, show) and the app performs them. The first SDK is Python; the protocol is small enough for any language.

## Consequences

- A plugin cannot crash, hang, or print its way into the window; the host reports and moves on. Isolation comes free from the process boundary.
- One process per plugin and one round trip per keystroke. The protocol stays one line each way, processes stay alive, and calls move off the UI thread in milestone 1.
- Plugins declare their own dependencies and Python version; uv builds each environment. The app carries no interpreter in milestone 0; how a bundle finds or carries Python is a milestone 3 design task.
- MCP was not chosen: it is built for model-to-tool calls, heavier than needed, and the standing constraints favour CLI-first surfaces. If plugins ever need to be reachable by agents, an MCP adapter can sit on top of this protocol.
