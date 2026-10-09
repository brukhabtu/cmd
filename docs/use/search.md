# The search plugin

Search your notes and documents from the launcher through tools you choose. The first is
[qmd](https://github.com/tobi/qmd), a local search engine for markdown; any other program
that takes the typed text as an argument and prints paths or hits can be added from the
config, with no code. Providers that share a keyword are searched at once and their hits
merged into one list. Decision 11 is the design.

!!! warning "Not yet tried on a Mac"
    The plugin is tested on Linux against qmd 2.8.3, the captures of its answers, and a
    fake provider. Nothing here has run on a Mac yet: where qmd and node sit after a
    Homebrew or npm install, the `PATH` a Dock launch gives, Open and Reveal in Finder, and
    the Obsidian link in the example below are all unchecked there.

## What it does

With the worked example below, both providers on `n`:

| You type | You see | Enter |
|---|---|---|
| `n offsite` | the notes qmd and ripgrep found, best first, each naming who found it | opens the file |
| `qmd offsite` | qmd's hits alone | opens the file |
| `n o` | "Search qmd, notes-rg": the text is shorter than `min_chars`, so nothing runs | nothing |
| `search` | each provider, its keywords and its last search, and every config problem | depends on the row |

Every keyword comes from the config. Typing anything that does not start with one of them
costs nothing: no program starts and no file is read. A search runs each selected provider
on its own thread with one deadline for all of them, so a slow provider never holds up the
others' hits.

## Install qmd and index your notes

qmd is a Node program, published on npm as `@tobilu/qmd`:

```sh
npm install -g @tobilu/qmd
qmd collection add ~/Notes --name notes
qmd collection add ~/Meetings --name meetings
qmd search --json --full-path -n 5 -- offsite
```

The last line is the call the plugin makes; if it prints a JSON list, the plugin will too.
`qmd collection list` shows what is indexed, and `qmd update` indexes what changed since.
The plugin uses only `qmd search`, qmd's keyword search: its `vsearch` and `query` modes
load language models on every call, and the config refuses them.

Then find the two paths the config needs:

```sh
command -v qmd     # the bin
command -v node    # its folder goes in env.PATH
```

## The config

`config.toml` in the plugin's config directory
(`~/Library/Application Support/cmd/plugin-config/search/`). The plugin reads it once at
start; saving it restarts the plugin. The smallest that works:

```toml
[[provider]]
name = "qmd"
kind = "qmd"
keywords = ["n"]
bin = "/opt/homebrew/bin/qmd"
env = { PATH = "/opt/homebrew/bin:/usr/bin:/bin" }
```

The worked example: qmd over two collections, and ripgrep over a folder as a second
provider, both on `n`:

```toml
status_keyword = "search"
deadline = 1.0
min_chars = 2

[[provider]]
name = "qmd"
kind = "qmd"
keywords = ["n", "qmd"]
bin = "/opt/homebrew/bin/qmd"
env = { PATH = "/opt/homebrew/bin:/usr/bin:/bin" }
collections = ["notes", "meetings"]
limit = 10
open = "obsidian://open?path={path}"

[[provider]]
name = "notes-rg"
kind = "command"
keywords = ["n", "grep"]
command = [
  "/opt/homebrew/bin/rg", "--files-with-matches", "--null", "--ignore-case",
  "--fixed-strings", "--sortr", "modified", "--glob", "*.{md,txt}",
  "--", "{text}", "/Users/you/Notes",
]
format = "paths"
exit_codes = [0, 1]
limit = 10
```

The paths are examples: put in what `command -v` printed on your Mac. For ripgrep,
`--fixed-strings` keeps the text from being read as a regular expression, `--sortr
modified` lists the note changed last first, and `exit_codes = [0, 1]` because ripgrep
exits 1 when nothing matches. `{limit}` would put the provider's limit into an argument
(`--max-count`, `fd --max-results`); a provider should limit itself, since the plugin keeps
whatever it prints until the deadline.

### Why `bin` and `env.PATH`

Opened from the Dock, cmd and its plugins get a bare `PATH`, so a bare `qmd` is not found.
And qmd's launcher starts with `#!/usr/bin/env node`: without the folder of the `node` qmd
was installed with on its `PATH`, it exits 127 with a line such as
`/usr/bin/env: 'node': No such file or directory` (the Linux wording, captured from qmd
2.8.3; the Mac's may differ). So `bin` is an absolute path, and `env` sets the `PATH` qmd runs with; the plugin starts it
as `/usr/bin/env PATH=... /opt/homebrew/bin/qmd search ...`. Without `env` the program is
started directly, with the plugin's own environment. Use the same `node` qmd was installed
with: another fails to load qmd's native modules.

### Every key

| Key | Must be set | Default | Rule |
|---|---|---|---|
| `status_keyword` | no | `"search"` | one word; no provider may use it |
| `deadline` | no | `1.0` | seconds, 0.5 to 1.5; one deadline for every provider of a keyword |
| `min_chars` | no | `2` | 1 to 10; shorter text after a keyword starts nothing |
| `provider.name` | yes | | letters, digits, `.`, `_`, `-`, at most 32; unique, case ignored |
| `provider.kind` | yes | | `qmd` or `command` |
| `provider.keywords` | yes | | a list of one or more words, case ignored; providers may share one |
| `provider.env` | no | the plugin's own environment | a table of text, such as `{ PATH = "..." }` |
| `provider.limit` | no | `10` | hits asked for and kept, 1 to 50 |
| `provider.open` | no | `"{uri}"` | what Enter opens for a file: a URL once `{uri}` (the `file://` URL), `{path}` (the path, percent-encoded but for `/`) and `{line}` (the hit's line, or 1) are filled; it holds `{uri}` or `{path}` |
| `bin` (qmd) | yes | | absolute path to qmd, without `=` |
| `collections` (qmd) | no | qmd's default collections | names; one `-c` each |
| `index` (qmd) | no | qmd's default index | passed as `--index` |
| `mode` (qmd) | no | `"search"` | `search` only |
| `command` (command) | yes | | the program, absolute, then its arguments; some argument holds `{text}` |
| `format` (command) | yes | | `paths` or `hits` |
| `exit_codes` (command) | no | `[0]` | the exit codes that mean the command answered |

!!! warning "A misspelt `index` searches an empty index"
    qmd answers `--index` with a name it does not know by creating a new, empty index and
    finding nothing in it. The plugin cannot tell, so when `index` is set the "No hits"
    row names the index it searched: check the spelling there first.

A key the schema does not have is an error, so a misspelt key is seen rather than ignored.
A bad provider is dropped and the rest work; an out-of-range `deadline` or `min_chars` uses
its default. Each problem is a row under `search` and on the keywords of the provider it
belongs to, and Enter on it opens the config directory. With no config at all, `search` says
where to create one. A config that does not parse shows the parser's message under `search`
and on the keywords of the last config that did. A provider whose `bin` or program is not
an executable file is kept, but starts nothing: the problem is its only row.

### The command kind

`command` runs any program, with no shell. In each argument `{text}` becomes the typed text
and `{limit}` the limit; nothing else in braces is touched, so a glob such as `*.{md,txt}`
passes as written. Put `--` before `{text}` where the tool takes one, so a text starting
with `-` is not read as an option. The order of what it prints is the rank. `format` says
how stdout is read:

- `paths`: one absolute path per line, or per NUL byte when the output holds one (`rg -l
  --null`, `mdfind -0`, `fd -0`). A relative path is skipped. The title is the file name.
- `hits`: one JSON array of hits, or one hit per line. A hit is an object such as
  `{"title": "Offsite budget", "path": "/Users/you/Notes/offsite.md", "line": 3,
  "snippet": "Budget approved by finance."}`, with a `title` or an absolute `path` at
  least; a `url` with a scheme for a hit that is not a file, and a `reference` that "Copy
  reference" copies. Other fields are ignored.

An exit code not in `exit_codes` is a problem row showing the first line of stderr; what
the command printed before it still counts.

## The rows

Hits come first, merged by rank: every provider's first hit, in config order, then every
second hit, and so on. Scores are ignored, since qmd's depends more on the corpus than on
the match. A file two providers both found is one row naming both (compared by real path,
so a folder reached through a symlink still matches). The subtitle is who found it and the
snippet, or the folder when there is none.

| Hit | Enter | Other actions |
|---|---|---|
| a file | Open (through `open`) | Reveal in Finder, Copy path, and Copy docid or Copy reference when it has one |
| a URL | Open | Copy URL |
| a qmd hit for a file no longer on disk | Copy docid | Copy qmd URI; run `qmd update` |
| a title alone | Copy text | |

After the hits, one row for each provider in trouble, so a failing or slow provider never
hides the others' hits:

| Row | Means |
|---|---|
| "qmd: Collection not found: nosuch", "exit 1; check this provider in config.toml" | the program failed; the title is the first line of its stderr |
| "qmd: /usr/bin/env: 'node': No such file or directory", "a program it needs is not on its PATH: set env.PATH" | exit 126 or 127: see [Why `bin` and `env.PATH`](#why-bin-and-envpath) |
| "notes-rg did not answer within 1.0 s" | its hits are left out |
| "notes-rg stopped at 1.0 s" | the hits above are those it printed by then |
| "notes-rg: 3 entries could not be read" | some of its output was not paths or hits; the subtitle says why |
| "notes-rg is resting after 3 slow answers, until 14:31" | it missed the deadline three times running, so it is left alone for 30 s |
| "No hits in qmd, notes-rg" | every provider answered, with nothing |

Enter on a problem row shows the command as it was run and the first lines of its stderr.
An answer is kept for 10 s, so typing the same text again starts nothing; an answer that
missed the deadline is not kept.
