---
id: decision-8
title: >-
  Plugins are found in a git-backed index and installed by cloning; PyPI can be a
  second source later
date: '2026-10-07 05:30'
status: proposed
---
## Context

A plugin is a directory: `cmd-plugin.toml`, a `pyproject.toml` that depends on `cmd-sdk`,
and a package. The launcher finds plugins in the per-user directory
(`~/Library/Application Support/cmd/plugins`), in `./plugins`, or in `CMD_PLUGINS`
(task 1.13), and today installing one means copying its directory there (the tutorial's
step 5). Task 1.26 asked how a person finds a plugin someone else wrote, and how it is
installed and kept up to date. Three shapes were weighed.

**A git-backed index.** A TOML file in this repository lists plugins by name, each with a
summary and where its code is. Listing is a pull request, so a maintainer reads the
plugin before it is listed. Installing clones into the plugin directory; updating moves
the clone forward. A plugin's repository is already the layout the tutorial builds, so
publishing is a push and a pull request. This is how Homebrew taps and the Raycast
extensions repository work.

**PyPI.** A plugin is a distribution with a keyword or an entry point. Installing resolves
and installs a release into an environment of its own; updating is a version bump. But
PyPI has no search a client can use to find plugins by keyword (the XML-RPC search is
gone and the simple index carries no metadata), so finding still needs an index somewhere;
the manifest would have to travel inside the wheel; and a ten-minute plugin would have to
be built and published to be installable, which is the friction the SDK tutorial exists
to avoid.

**Both.** An index whose entries name either a git repository or a PyPI distribution,
with the installer dispatching on the kind.

## Decision

Plugins are found in a git-backed index and installed by cloning. The index is one TOML
file in this repository, `plugins/index.toml`, with one table per plugin: `name` (the
manifest's name, and the directory it installs to), `summary`, `source` (a git URL),
`ref` (a tag or a commit, required) and `subdirectory` (optional, for a plugin that
lives inside a larger repository, as this repository's own plugins do). Listing a plugin
is a pull request against the file, and so is moving its `ref`; CI checks the file's
shape and pins every tag to the commit it pointed at when it was reviewed, since a tag can
be moved and a commit cannot. The `ref` is what makes the listing mean something: what
someone here read is what installs, and what an update moves to, until a pull request
says otherwise. An install writes where it came from (the kind of source, the index name,
the URL and the ref) to `.cmd-install.toml` in the plugin directory, which `update` and
`list` read; the name is hidden so the file watcher ignores it.

The app's own binary takes the subcommands, so nothing else is installed. It reads its
arguments before any window or hotkey exists, so `cmd plugin ...` never opens the
launcher. The subcommands write to the per-user directory, or to the first entry of
`CMD_PLUGINS` when that is set.

- `cmd plugin install <what>` where `<what>` is a name from the index, a git URL, a
  GitHub `owner/name`, or a local path. An index entry is fetched at its `ref` (a shallow
  fetch of that commit into a fresh repository, since `git clone --branch` takes only
  tags and branches) and, with `subdirectory`, that directory is what is kept; a URL or
  `owner/name` is cloned shallowly at its default branch; a path is copied. The install
  refuses a source without a `cmd-plugin.toml`, refuses a manifest whose name is not the
  directory it would install to, and names a directory that is already there instead of
  overwriting it.
- `cmd plugin update [name]` moves an index-installed plugin to the index's current `ref`
  and nothing else, and fast-forwards a plugin installed from a URL or `owner/name` to its
  default branch. A fast-forward that fails, because the person has edited the clone, is
  reported and changes nothing, as is an index entry whose `source` has changed since the
  install: remove and install again, deliberately. A plugin installed from a path has
  nothing to update and says so.
- `cmd plugin remove <name>` deletes the directory.
- `cmd plugin list` shows what is installed, from where and at what, and, with the index,
  what is not.

Installing a plugin means running someone's code with the person's rights, from the
index or from any URL alike; the index is a recommendation with a reviewed `ref`, not a
sandbox, and the command says so once before the first install from outside the index.

Two plugins with one name cannot both run: the host loads the first it finds in the
order of its plugin directories and reports the second as a start failure naming both
directories, so a stale copy in `./plugins` or `CMD_PLUGINS` is seen, not silently
shadowed.

The index entry's shape leaves room for a second source kind. PyPI becomes one when a
plugin author asks for it with a reason the git source cannot meet; that is a new
decision with that evidence, not this one.

## Consequences

- Tasks to file: the `plugin` subcommands on the app binary with index, git and path
  sources; `plugins/index.toml` with its CI check, listing this repository's own plugins
  by `subdirectory`; `cmd-doctor` folded in as `cmd plugin doctor <dir>` once the
  subcommands exist, so there is one tool. The Homebrew cask (1.25) links the binary as
  `cmd` so the subcommands are on PATH; the tutorial's step 5 gains
  `cmd plugin install owner/name`.
- Task 1.33 (filed from this decision): the host refuses the second plugin of a name.
- An update that changes files is picked up by the plugin's reload (task 1.14) when the
  app is running; only a new install waits on task 1.31 (plugins that appear after
  launch), and until that lands the command says to open the launcher again.
- Decision 7 holds: an installed plugin runs with the bundle's uv, which makes its
  environment on the first query.
- Nothing here needs an account, a server, or a signing key; those come, if ever, with
  the second source kind.
