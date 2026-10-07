# cmd

A launcher for macOS in the place of Spotlight. Rust core, GPUI window, plugins in Python.

- **How we work** is the `philosophy` plugin, vendored at `.claude/plugins/bruk-philosophy`
  and enabled by `.claude/settings.json`. Its constraints arrive every session. Anything
  bigger than a handful of tool calls goes through its `work-loop` skill and the board.
- **The board** is `backlog/` (Backlog.md). `backlog task list --plain`. Statuses, types and
  size labels follow the work-loop's `references/board-frontmatter.md`.
- **Architecture** is `docs/architecture.md`, with the LikeC4 model in `docs/architecture/`.
- **The plugin protocol** is `docs/plugin-protocol.md`. Its Rust side, its Python side and
  the adapter test change together.
- **Skills** are proposed at milestone boundaries and accepted only by eval: `docs/skills.md`.
- **Checks**: `scripts/check.sh` runs what CI runs. Run it before pushing.
- **Docs**: the MkDocs site is `mkdocs.yml` and `docs/`; `scripts/docs_gen.py` generates the
  reference pages from the code. `scripts/docs.sh` builds it, strict, and `check.sh` runs it.
  Releases alone publish it, to GitHub Pages (`.github/workflows/pages.yml`).
- **Layout**: `crates/` (Cargo workspace: `cmd-core` pure logic, `cmd-host` plugin
  processes, `cmd-app` the GPUI window), `python/cmd-sdk` (the plugin SDK),
  `plugins/` (Python plugins, one directory each with a `cmd-plugin.toml`),
  `.claude/plugins/` (Claude Code plugins).
- **Linux cannot build `cmd-app`**: a `libc`/`xattr` clash below GPUI. Use
  `cargo test --workspace --exclude cmd-app` there; CI builds the app on macOS.
  `scripts/linux-app-workspace.sh` makes a scratch workspace outside the repository where
  it does build; `scripts/screenshots.sh` runs the window from it for the docs.
