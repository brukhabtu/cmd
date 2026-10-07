---
id: decision-7
title: >-
  cmd.app carries uv and lets it manage one Python; plugins need nothing else on
  the machine
date: '2026-10-07 05:25'
status: proposed
---
## Context

A plugin is a directory with `cmd-plugin.toml` whose `command` is, for every plugin so
far, `uv run <entry>`: uv reads the plugin's `pyproject.toml`, makes its environment and
runs it. So cmd.app needs uv, and uv needs a Python that satisfies the plugin's
`requires-python` (3.15, decision 2). Task 1.22 asked which of three ways to get there the
bundle should take: require uv on PATH, carry uv in the bundle, or carry a Python in the
bundle.

What was measured, on a Linux x86_64 container with uv 0.11.32. A Mac will differ in the
small numbers, not in the shape; the Mac figures are owed before task 1.23 closes.

| Measurement | Result |
|---|---|
| The uv binary | 66 MB |
| A uv-managed CPython 3.15: download and unpack, on this network | 5.1 s; 111 MB on disk |
| The websearch plugin's own environment (cmd-sdk only) | 236 KB, 41 files |
| First `uv run` of that plugin outside the workspace: cold cache, no environment, Python present | 0.25 s |
| Second and third `uv run` of it | 0.13 s, 0.07 s |
| The environment's Python directly | 0.04 s |

The Python is the only expensive thing: a machine's first launch costs one Python
download, once, and every plugin after that costs a quarter of a second the first time
and a tenth after.

## Options

**Require uv on PATH.** Nothing in the bundle. But an app launched from the Dock or at
login has launchd's PATH (`/usr/bin:/bin:/usr/sbin:/sbin`), not the shell's, so Homebrew's
`/opt/homebrew/bin/uv` and the installer's `~/.local/bin/uv` are invisible unless the app
searches those places itself or reads the login shell's PATH. The person installs uv by
hand before any plugin runs, and the uv version is whatever they have, so a change in uv
reaches cmd through their updates, not ours.

**Carry uv in the bundle.** One static binary (66 MB here), signed with the app, so
notarisation changes in size and not in kind. uv downloads a Python on first use and keeps
it where `UV_PYTHON_INSTALL_DIR` says. The first launch needs the network for one download
(5 s here); every launch after that is offline. The uv version is ours, pinned in the
bundle and updated with the app.

**Carry a Python in the bundle.** A python-build-standalone tree (111 MB here) or the
python.org framework inside `Contents/Frameworks`, so the first launch works offline.
Every dylib and extension module must be signed, which is hundreds of files per build,
and the bundle grows by the whole runtime. It does not remove uv: plugins still need
something to read `pyproject.toml` and make an environment, so this is the second option
plus a Python, at roughly three times the size.

## Decision

cmd.app carries uv and nothing else. The app puts the bundle's own directory first on
the PATH it starts plugins with, so `uv` in a manifest resolves to `Contents/MacOS/uv`,
and sets `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` under
`~/Library/Application Support/cmd/` and `UV_PYTHON_PREFERENCE=only-managed`, so the
Python plugins run on is the one uv installed, not whatever the machine has. On first
launch the window says a Python is being fetched; the describe timeout (60 s) is already
sized for a first `uv run`. A uv on PATH is neither required nor used.

## Consequences

- Task 1.23 (the bundle built by CI) copies the uv release binary for the target
  architecture into the bundle and signs it with the app; the Homebrew cask (1.25)
  carries nothing more.
- The host sets the PATH and the three variables when it starts a plugin, and
  `cmd-doctor` does the same, so a plugin behaves identically under both. Plugins
  outside this repository keep `uv run` as their command and need no change.
- A machine's first launch fetches Python once; the window's start-trouble and waiting
  lines (1.30, 1.11) carry that. An offline first launch is not supported; if one is ever
  needed, the third option is the answer, and this decision is revisited with that
  evidence.
- The bundle grows by uv. If the app must be smaller than that, the first option is the
  fallback, with a search of the known install locations.
- Measured on a Mac before 1.23 closes: the arm64 uv binary, the Python download on a
  home connection, and the first launch of each plugin in the bundle.
