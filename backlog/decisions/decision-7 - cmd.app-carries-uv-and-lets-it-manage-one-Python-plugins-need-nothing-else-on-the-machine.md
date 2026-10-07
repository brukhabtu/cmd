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

What was measured, on a Linux x86_64 container with uv 0.11.32 and a release build of
the app, with the calculator and websearch plugins copied outside the workspace (cmd-sdk
as a path source) and described through `cmd-doctor` one after the other, as
`Host::start` does. A Mac will differ in the small numbers, not in the shape; the Mac
figures are owed before task 1.23 closes.

| Measurement | Result |
|---|---|
| First launch, end to end: no managed Python, cold uv cache, `uv python install 3.15` then both plugins described | 5.8 s |
| The same two describes right after, warm | 0.34 s |
| `uv python install 3.15` when it is already there | 0.06 s |
| A plugin's own environment, cmd-sdk only | 192 KB |
| The managed CPython 3.15 on disk | 112 MB |
| The uv binary | 66 MB |
| The `cmd` binary itself, release build | 26 MB |
| The bundle: `cmd` plus uv | 92 MB; with a Python inside as well, 204 MB |

The Python is the only expensive thing: a machine's first launch costs one download,
once, and every plugin after that costs a tenth of a second or so on each launch.

One finding shapes the decision: with `UV_PYTHON_PREFERENCE=only-managed` and no managed
Python, `uv run` did not fetch one. It refuses a version its embedded download list does
not know (3.15 was a pre-release when this uv was built), so a first launch that relies on
`uv run`'s automatic download fails with "No interpreter found for Python >=3.15 in managed
installations". An explicit `uv python install 3.15` fetches it, and is a no-op when it is
there.

## Options

**Require uv on PATH.** Nothing in the bundle. But an app launched from the Dock or at
login has launchd's PATH (`/usr/bin:/bin:/usr/sbin:/sbin`), not the shell's, so Homebrew's
`/opt/homebrew/bin/uv` and the installer's `~/.local/bin/uv` are invisible unless the app
searches those places itself or reads the login shell's PATH. The person installs uv by
hand before any plugin runs, and the uv version is whatever they have, so a change in uv
reaches cmd through their updates, not ours.

**Carry uv in the bundle.** One static binary (66 MB here), signed with the app, so
notarisation changes in size and not in kind. uv fetches a Python on the first launch and
keeps it where `UV_PYTHON_INSTALL_DIR` says (5.8 s here, end to end); every launch after
that is offline, as long as uv's cache already holds what each plugin's environment needs,
so a plugin added later with new dependencies needs the network once. The uv version is
ours, pinned in the bundle and updated with the app.

**Carry a Python in the bundle.** A python-build-standalone tree (112 MB here) or the
python.org framework inside `Contents/Frameworks`, so the first launch works offline.
Every dylib and extension module must be signed, which is hundreds of files per build,
and the bundle grows by the whole runtime. It does not remove uv: plugins still need
something to read `pyproject.toml` and make an environment, so this is the second option
plus a Python, and the bundle total below grows by that 112 MB.

## Decision

cmd.app carries uv and nothing else. When the app runs from inside a bundle (its
executable is under `Contents/MacOS`), the host puts that directory first on the PATH it
starts plugins with, so `uv` in a manifest resolves to `Contents/MacOS/uv`, and sets
`UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` under `~/Library/Application Support/cmd/` and
`UV_PYTHON_PREFERENCE=only-managed`, so the Python plugins run on is the one uv installed,
not whatever the machine has. Before the first plugin starts, the app runs
`uv python install 3.15` without linking an executable into `~/.local/bin`: a one-time
fetch the first time, and 0.06 s every time after, so no launch relies on `uv run`'s
automatic download. The window says a Python is being fetched while that runs (task 1.32
is what puts the window on screen before the host starts). A uv on PATH is neither
required nor used by the bundle.

Outside a bundle, nothing is set: `cmd-doctor`, the adapter tests and a `cargo run` from a
clone use the developer's own uv and Python, as they do today.

## Consequences

- Task 1.23 (the bundle built by CI) copies the uv release binary for the target
  architecture into the bundle and signs it with the app; the bundled uv must be a release
  that knows the Python version the plugins need, or the first launch fails as above. The
  Homebrew cask (1.25) carries nothing more.
- Task 1.32: `main()` starts the host before the window exists today, so on a first launch
  nothing is on screen until every handshake, including the Python fetch, is done. The
  window must open first and the host start beside it, or the "fetching Python" line above
  cannot be shown.
- The host applies the PATH and the three variables only inside a bundle, so a plugin
  behaves the same under `cmd-doctor` and under the app, each in its own environment.
  Plugins outside this repository keep `uv run` as their command and need no change.
- An offline first launch is not supported; if one is ever needed, the third option is the
  answer, and this decision is revisited with that evidence.
- The bundle is the app plus uv: 92 MB here against 26 MB for the app alone. If it must
  be smaller than that, the first option is the fallback, with a search of the known
  install locations.
- Measured on a Mac before 1.23 closes: the arm64 uv binary, the Python fetch on a home
  connection, and the first launch of each plugin in the bundle.
