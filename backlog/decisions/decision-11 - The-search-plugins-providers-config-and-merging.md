---
id: decision-11
title: 'The search plugin''s providers, config and merging'
date: '2026-10-09 13:59'
status: proposed
---
## Context

Task 3 wants qmd's search in the launcher, and other search tools beside it, each chosen
and configured by the owner: one plugin, `search`, configured with providers, as draft 8
argues for feeds. The lead's spike on task 3 ran the real qmd 2.8.3; this decision rests on
it and on further runs of the same install, listed at the end. Decision 10 is the
precedent for a configured plugin, and this decision follows it (the config read once at
start, a row and never an exception for a config problem, its own keyword matching until
draft 5, a query path that never raises) except where it says otherwise.

One departure from decision 9 comes first. Decision 9 says a provider never runs in
`query`: a thread refreshes a cache and `query` reads it. That fits a feed, whose answer
does not depend on the typed text. A search provider's answer is the answer to the typed
text, which no cache can hold ahead of time, so **a search provider runs in `query`**,
under the deadline below. Decision 9's other provider rules hold: an absolute path from
the config, and credentials that are the provider's own.

## Decision

### Providers in code

A pure core and a thin shell, as the vault has. `search.schema` turns the config into
settings; `search.kinds.qmd` and `search.kinds.command` are the two kinds; `search.merge`
turns outcomes into rows; `search.plugin` is the shell (start, `query`, `run`, threads,
`call`, the cache). A kind is a module with these names, and `search.kinds.KINDS` maps
the config's `kind` to it, so a new kind is one module and one line:

```python
KEYS: frozenset[str]  # the keys this kind adds to a [[provider]] table
REFERENCE: str        # the title of the action that copies Hit.reference ("Copy docid")

def parse(table: Mapping[str, Any]) -> Settings: ...  # its own keys; raises Invalid(message)
def executable(settings: Settings) -> str: ...        # the program, checked at start
def arguments(settings: Settings, text: str, limit: int) -> tuple[str, ...]: ...
def read(settings: Settings, finished: CallResult, cwd: Path) -> Outcome: ...
```

The types they share, in `search.kinds`:

```python
@dataclass(frozen=True, slots=True)
class Hit:
    title: str
    path: str | None = None       # absolute; None when the hit has no file on disk
    url: str | None = None        # with a scheme, for a hit that is not a file
    snippet: str = ""             # plain text, no header line
    line: int | None = None       # 1-based line of the snippet in the file
    reference: str | None = None  # the provider's own handle for the hit (qmd's docid)

@dataclass(frozen=True, slots=True)
class Found:
    hits: tuple[Hit, ...]         # best first
    skipped: int = 0              # entries of the output that could not be read
    cut: bool = False             # the deadline passed: these are the hits read by then

@dataclass(frozen=True, slots=True)
class Failed:
    message: str                  # one line, for the row's title
    detail: str = ""              # the command and stderr's first lines, for Enter

type Outcome = Found | Failed
```

`read` gets the whole `CallResult`, a timed-out one too, so a kind that reads line by line
keeps what arrived and one that cannot returns `Failed`. An exception from a kind becomes
`Failed` in the shell. Everything else is the shell's: the environment, the call, the
threads, the deadline, the cache and the rows.

**Rank, never score.** The plugin ignores every score a provider prints. qmd's is
`|bm25| / (1 + |bm25|)` rounded to two places (`searchFTS` in qmd's `store.ts`), so it
follows the corpus's term statistics rather than the match: a clear match scored 0 in the
three-note test corpus, where its words are in most notes, and two places make ties. The
order a provider printed is the signal (qmd orders by raw BM25, then path). Across
providers the merged order is by rank, then by the provider's place in the config: every
provider's first hit, in config order, then every second hit, and so on. Rows carry no
`score`, so the host keeps the plugin's order and ranks the rows above the scored rows of
other keyword-less plugins (Routing in `docs/plugin-protocol.md`), as the vault's rows are.

### The qmd kind

The call is `<bin> search --json --full-path -n <limit> [-c <collection>]... [--index
<index>] -- <text>`. The `--` is always there: a text that starts with `-` is otherwise a
usage error. `--full-path` makes qmd print the file's real path, so the plugin never reads
qmd's own config to resolve a `qmd://` URI.

| qmd answers | The kind reads |
|---|---|
| exit 0, a JSON array | each element an object with a string `file`, or skipped and counted; `title` (else the file name), `snippet`, `line`, `docid` as `reference`; `score` and `context` ignored |
| `file` starts with `/` | the path |
| `file` starts with `./` | the file is under qmd's working directory, which is the plugin's own (the host starts it there): the path is that directory joined to the rest |
| `file` starts with `qmd://` | the file was not on disk (moved or deleted since qmd's last index; qmd says so on stderr and keeps the `docid`): no path |
| the snippet | its first line dropped when it matches `^@@ -\d+(,\d+)? @@`; a line `# <title>` and blank lines dropped; whitespace collapsed |
| exit 0, not a JSON array | `Failed("answer is not qmd's JSON: <parser message>")` |
| any other exit | `Failed(<stderr's first line, or "exited with N">)` |
| timed out | `Failed`: half a JSON array is no answer |

### The command kind

`command` is the program, absolute, and its arguments; no shell. In each argument
`{text}` becomes the typed text and `{limit}` the limit, and nothing else in braces is
touched, so a glob such as `*.{md,txt}` passes as written. (The vault refuses a
placeholder it does not know; here braces belong to the tools.) Some argument must hold
`{text}`. The person puts `--` before `{text}` where the tool takes one.

`format` says how stdout is read, and the output's order is the rank:

- `paths`: one absolute path per line, or per NUL when the output holds a NUL byte (`rg
  -l --null`, `mdfind -0`, `fd -0`). A relative path is skipped. The title is the file
  name; there is no snippet.
- `hits`: one JSON array of hits, or one hit per line (JSON lines). A hit is an object:
  `{"title": "Offsite budget", "path": "/Users/bruk/Notes/offsite.md", "line": 3,
  "snippet": "Budget approved by finance."}`, with `title` or `path` at least, `path`
  absolute, `url` with a scheme, and `reference` copied by "Copy reference". Other fields
  are ignored, so a tool may print more. An entry that does not fit is skipped and counted.

An exit code in `exit_codes` is an answer (ripgrep and grep exit 1 for no match); any
other is `Failed` with stderr's first line, and the complete entries it printed before
failing are still hits, shown above the problem row (ripgrep exits 2 for one unreadable
file and still prints the rest). At the deadline a `paths` or JSON-lines
answer keeps its complete lines and is `cut`; an array is `Failed`. Output whose every
entry was skipped is `Failed("N entries are not <format>: <first problem>")`.

**Decoding and size.** A path is decoded as the file system does (`os.fsdecode`, so a name
that is not UTF-8 still names its file), any other text as UTF-8 with replacement. The kind
reads no more than `4 * limit` entries and stops; the bytes `call` has already kept are
bounded by the deadline and not by a cap, since `call` has none: a command should limit
itself with `{limit}` (ripgrep's `--max-count`, `fd --max-results`), and a cap in `call` is
a follow-up for the SDK, not this plugin.

### The process's environment

The SDK's `call` cannot set an environment, and the plugin's own, from a Dock launch,
has a bare PATH. A provider's `env` table is handed over by starting the program through
`env`: the argv becomes `/usr/bin/env K=V ... <program> <arguments>`. `/usr/bin/env` is on
every Mac and execs the program, so no extra process holds the pipes. Without `env` the
program is started directly. For qmd, PATH must hold the `node` that qmd was installed
with: its launcher is `#!/usr/bin/env node`, and another Node fails to load qmd's native
modules.

### The config

`config.toml` in the plugin's config directory, read once at start through the SDK's
`config()`. A change restarts the plugin (decision 9), so the query path never reads it.
The worked example: qmd and a ripgrep over a folder, both on `n`.

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
mode = "search"
limit = 10
open = "obsidian://open?path={path}"

[[provider]]
name = "notes-rg"
kind = "command"
keywords = ["n", "grep"]
command = [
  "/opt/homebrew/bin/rg", "--files-with-matches", "--null", "--ignore-case",
  "--fixed-strings", "--sortr", "modified", "--glob", "*.{md,txt}",
  "--", "{text}", "/Users/bruk/Notes",
]
format = "paths"
exit_codes = [0, 1]
limit = 10
```

`n offsite` searches both at once, `qmd offsite` qmd alone, `grep offsite` ripgrep alone.
For ripgrep, `--fixed-strings` keeps the text from being a regular expression, and
`--sortr modified` puts the note changed last first, which is what its rank then means,
and makes the order stable at the cost of ripgrep's parallel walk. ripgrep exits 1 for no
match and 2 for an error. The smallest config that works:

```toml
[[provider]]
name = "qmd"
kind = "qmd"
keywords = ["n"]
bin = "/opt/homebrew/bin/qmd"
env = { PATH = "/opt/homebrew/bin:/usr/bin:/bin" }
```

The paths are examples: where qmd, node and ripgrep live is the owner's Mac's to say, and
`bin` has no default for the reason decision 10 gives.

| Key | Must be set | Default | Rule |
|---|---|---|---|
| `status_keyword` | no | `"search"` | one word; shows the providers and every config problem; no provider may use it |
| `deadline` | no | `1.0` | seconds, 0.5 to 1.5 (qmd's warm median is 0.2 s); one deadline for every provider of a keyword, which run at once |
| `min_chars` | no | `2` | 1 to 10; a text after the keyword shorter than this starts no process |
| `provider.name` | yes | | letters, digits, `.`, `_`, `-`, at most 32; unique, ASCII case ignored; named in every row |
| `provider.kind` | yes | | `qmd` or `command` |
| `provider.keywords` | yes | | a list of one or more words, ASCII case ignored; providers may share a word. A provider with none is refused: it could only run on every keystroke of all text |
| `provider.env` | no | none: the plugin's own environment | a table of strings; names match `[A-Za-z_][A-Za-z0-9_]*` |
| `provider.limit` | no | `10` | hits asked for and kept, 1 to 50 |
| `provider.open` | no | `"{uri}"` | what Enter opens for a hit with a path: a URL with a scheme after filling `{uri}` (the `file://` URL), `{path}` (the path, percent-encoded but for `/`) and `{line}` (the hit's line, or 1); it holds `{uri}` or `{path}`; each placeholder is filled once, so a URL embedded in another URL's query is not supported |
| `bin` (qmd) | yes | | absolute path to an executable file, without `=` (env would take it for a variable) |
| `collections` (qmd) | no | `[]`: qmd's default collections | names, none starting with `-`; one `-c` each |
| `index` (qmd) | no | none: qmd's default index | letters, digits, `.`, `_`, `-`; passed as `--index` |
| `mode` (qmd) | no | `"search"` | `search`. `vsearch` and `query` are refused with a row naming this decision; anything else is refused as unknown |
| `command` (command) | yes | | a list; the first item an absolute executable file without `=`; `{text}` in some argument |
| `format` (command) | yes | | `paths` or `hits`; output cannot be guessed |
| `exit_codes` (command) | no | `[0]` | integers 0 to 255 that mean the command answered |

A key the schema does not have is an error, as in decision 10, so a misspelt key is seen.
A config problem is a row, never an exception, and never stops what still works:

| Problem | The plugin | The person sees |
|---|---|---|
| no `config.toml`, or an empty one | starts with no providers | on the status keyword: "No config: create config.toml in <directory>"; Enter opens the directory |
| it does not parse or cannot be read (`ConfigError`) | starts with no providers | the SDK's message, on the status keyword and on each keyword of the last config that parsed (kept in the data directory as `keywords.json`) |
| a provider is invalid | drops it; the rest work | "<name>: <problem>" on its keywords, when they parsed, and on the status keyword |
| its program is not an absolute, executable file | keeps it, starts nothing for it | that problem, as its only row, on each of its keywords |
| a top-level value is out of range | uses its default | the problem, on the status keyword |
| the SDK cannot find the config or data directory | starts with no providers | the SDK's message, on the status keyword |

Enter on a config problem opens the config directory, made first if missing, as the
vault does.

### Keywords and the query path

As decision 10: `describe` declares no keyword, so the host sends every text whose first
word is no other plugin's keyword. The plugin takes the first word and folds its ASCII
case. **A first word that is no keyword of its own gets `{"items": []}` at once**, with no
process, no file read and no lock. The status keyword shows each provider (its kind, its
keywords, its last outcome) and every config problem. A provider keyword selects every
provider that lists it, in config order; the rest of the text, trimmed, is what they
search.

What keeps a process from starting on every keystroke, beyond the host, which sends one
request at a time and asks only the newest of the queries that queued meanwhile:

- **A minimum length.** A text shorter than `min_chars` gets one row, "Search qmd,
  notes-rg", "Type at least 2 characters after n", and starts nothing.
- **A short cache.** Each provider's answer for a text is kept 10 s (at most 64 kept), so
  backspacing over a word and typing it again starts nothing. Only the answer of a call
  that finished in time is kept, hits or a failure message alike. A call that missed the
  deadline, cut or not, is not kept, so typing the text again tries again.
- **A rest for a hung provider.** A provider whose last three calls all missed the
  deadline (the call came back `timed_out`, with hits kept or not) starts nothing for 30 s and shows "notes-rg is resting after 3 slow answers, until
  14:31". A call that finished in time sets the count back to 0, even if it then spent
  `call`'s grace draining pipes; an answer from the cache is no call and changes nothing. Without it one hung tool would cost
  every keystroke on its keyword the whole deadline.
- **No delay before a search.** The plugin cannot see the keystroke that follows, so
  waiting would only make every answer later.

These three numbers live in the code.

**One deadline, in parallel.** Each selected provider not answered from the cache and not
resting gets a daemon thread, which builds the argv and calls `call(argv, deadline,
kill_on_timeout=True)`; the kill takes what the provider started with it. `query` waits
for the threads until `deadline + 1.0` s after it began (the 1 s is `call`'s grace for
pipes a grandchild holds open), which is at most 2.5 s, inside the host's 3 s. A thread
still running then counts as a provider that did not answer; whatever it brings later is
dropped. **`query` never raises**: its body is one `try`, and an exception becomes one row,
"search: <exception>: <message>", and goes to stderr.

**Merging.** Hits are merged in the order above. Two hits are one when their paths are the
same file (`os.path.realpath`, which reads only the file system's metadata, for at most
the hits kept, and run in each provider's own thread, so the deadline covers it and a path
that is not resolved by then is compared as written: qmd prints real paths, ripgrep prints them as reached under the folder it
was given, perhaps through a symlink), or when they have the same `url`; hits with
neither never collapse. The collapsed row sits at its best rank, takes title, snippet,
line and `open` from that provider and the reference from whichever has one, and names
every provider. After the hits come the problem rows, one per provider, so a failing,
slow or resting provider never hides the others' hits; when every provider answered with
none, one row says "No hits in qmd, notes-rg".

| What happened | Row title | Subtitle |
|---|---|---|
| exit not among the answers | "qmd: Collection not found: nosuch" | "exit 1; check this provider in config.toml" |
| exit 126 or 127 | "qmd: /usr/bin/env: 'node': No such file or directory" | "a program it needs is not on its PATH: set env.PATH" |
| the program would not start (`OSError`) | "qmd: cannot run /opt/homebrew/bin/qmd: No such file or directory" | "check bin in config.toml" |
| no answer by the deadline | "notes-rg did not answer within 1.0 s" | "its hits are left out; the others' are above" |
| cut at the deadline | "notes-rg stopped at 1.0 s" | "its hits above are those it found by then" |
| unreadable output | "qmd: answer is not qmd's JSON: <parser message>" | "exit 0" |
| entries skipped | "notes-rg: 3 entries could not be read" | the first problem |
| resting | "notes-rg is resting after 3 slow answers, until 14:31" | "its hits are left out" |

Enter on any of these shows the command as run and stderr's first five lines (`show`).

### Rows, Enter and the other actions

| Hit | Title | Subtitle | Icon | Actions, Enter first |
|---|---|---|---|---|
| with a path | the hit's title | "qmd, notes-rg: <snippet>", or the folder with `~` when there is no snippet | `PathIcon(path)` | Open; Reveal in Finder; Copy path; Copy docid (or the kind's `REFERENCE`) when it has a reference |
| with a URL, no path | the title | "<provider>: <url>" | `SymbolIcon("link")` | Open; Copy URL |
| a qmd hit not on disk (`qmd://`) | the title | "qmd: not on disk since qmd last indexed it; run qmd update" | `SymbolIcon("questionmark.folder")` | Copy docid; Copy qmd URI |
| neither (a `hits` entry with a title alone) | the title | "<provider>: <snippet>" | `SymbolIcon("doc.text")` | Copy text |

- **Open** returns `open` with the provider's `open` filled in, after `run` checks that
  the file is still there; a file gone since the search shows "<path> is not there any
  more" (for qmd, "run qmd update"). A URL hit opens its URL.
- **Reveal in Finder** runs `/usr/bin/open -R <path>` with a 5 s deadline, as the files
  plugin does.
- **Copy path** copies the absolute path; `qmd get <path>` reads the note, so it also
  serves where a docid would.
- **Copy docid** copies qmd's docid as qmd prints it (`#75ebe1`), which `qmd get` takes.
  Under `--full-path` qmd leaves the docid out for a file it found on disk, so only a hit
  not on disk has one. For that hit, which has no path, Enter copies the docid: it is the
  handle qmd still has.
- An item's id is a small JSON object holding what `run` needs (path, open target, URL,
  reference, qmd URI, text), so `run` keeps no memory of the query and survives a restart
  between the two. The object also names the providers that found the hit and its place in
  the merged order, so no two rows share an id. The other rows have fixed ids: `status`,
  `hint:min`, `config:<n>` for the nth config problem, `problem:<provider>` for a
  provider's failure and `none` for the row that says there were no hits.

### qmd's slow modes

`vsearch` and `query` load language models in every process (an embedding model, a 1.7B
query-expansion model and a reranker). Their time is **unmeasured**: the test install has
no models, and they were not downloaded. They stay off the query path, and `mode` refuses
them. A later slice could put them on it only if all of these hold:

1. A warm server holds the models: `qmd mcp --http --daemon`, whose README says the models
   stay loaded and its contexts are recreated in about 1 s after 5 min idle. The person or
   launchd starts it; `query` never starts a long-lived process.
2. A new kind, `qmd-http`, asks `POST http://localhost:8181/query` from the plugin's own
   process with a timeout, so no process starts per keystroke, and shows a stopped daemon
   (`GET /health`) as a row.
3. On the owner's Mac, the 95th percentile of `/query` over his notes, reranking on and
   off and including the recreation after idle, is at most half the deadline.
4. The kind finds paths: the HTTP answer carries `qmd://` URIs only, so it needs each
   collection's folder. That is the slice's own design question.

Even then a slow mode belongs on a keyword shared with a `search` provider, whose hits
arrive whatever the slow one does. Enter cannot run it instead: `run` returns one effect,
never rows. **The first slice builds `mode = "search"` only**; a later one adds the
`qmd-http` kind and, if the owner wants a docid for every hit, a `qmd get <path> -l 1` in
`run`, whose first line is `qmd://notes/offsite.md  #75ebe1`.

### What task 3.2 tests

1. Each captured qmd answer through `qmd.read`: two hits, one hit, none, full paths,
   `./relative` under the working directory (resolved against the `cwd` given), and
   `qmd://` with a docid as the shape of a hit not on disk; each stderr capture (collection
   not found, usage, no node) as a `Failed` with that line.
2. The snippet: both header shapes dropped, the `# <title>` line dropped, a snippet without
   a header left whole.
3. qmd's argv: `--` before every text, one starting with `-` included; `-c` per
   collection; `--index` only when set; `-n` the limit; the `env` prefix when `env` is set
   and the bare program when not.
4. Rank over score: hits scored 0 and 0.49 keep the printed order; the interleaving across
   two providers; ties going to config order.
5. The command kind: `{text}` and `{limit}` filled, other braces left alone, `{text}`
   required; `paths` split by newline and by NUL, a relative path skipped; `hits` as an
   array and as JSON lines, a bad entry skipped and counted, all bad as `Failed`;
   `exit_codes`; exit 2 with stderr as `Failed`.
6. The schema: every key's default and rule from the table; an unknown key; a provider
   without keywords; a shared keyword; a keyword equal to the status keyword; a repeated
   name; `mode` as `query`, `vsearch` and nonsense; an out-of-range deadline falling back;
   both TOML examples here parsing into the settings expected.
7. Every config problem as its row: missing, empty, unparseable with stale keywords, one
   invalid provider beside a valid one, a program that is not executable.
8. Merging: duplicates by real path (through a symlinked folder) and by URL, both
   providers named; problem rows after the hits; the no-hits row.
9. The query path with a fake provider, an executable script in the tests that records
   each start in a file and, by its arguments, answers, sleeps past the deadline, exits 2
   with stderr, prints garbage, prints some paths and then sleeps, or leaves a grandchild
   holding stdout; and a program that does not exist. In each case `query` answers within
   2.5 s, never raises, and keeps the other provider's hits. A first word that is no
   keyword, and a text under `min_chars`, start nothing; a repeated text inside 10 s starts
   nothing; three timeouts rest a provider and it comes back after 30 s (clock injected).
10. `run`: each action of each row shape; the `open` template with a path holding a space,
    `#` and `%`; a path gone since the search; ids decoded with no state.
11. `serve` over `StringIO`: `describe` has no keyword, and a query and a run round-trip.
12. The real qmd, only when `CMD_TEST_QMD` names a qmd binary (its PATH in
    `CMD_TEST_QMD_PATH`): a temporary folder indexed under a temporary HOME and XDG
    directories handed over through the provider's `env`, then a search through the plugin
    that finds the note and opens its path. Skipped, saying why, otherwise.

### Verified by running qmd

On the lead's install (qmd 2.8.3, Linux, isolated HOME, three notes in two collections):
warm `qmd search --json --full-path` took 0.20 s median, 0.22 s at the 95th percentile and
0.24 s at most over 20 runs; the argv above, with `-c` twice, `--index index` and `--`,
answers as described; `-- -offsite` answers `[]` where `-x` without `--` is a usage
error; texts with FTS syntax (`"unbalanced`, `NEAR(`, `*`, `(`, `foo:bar`) answer `[]`
or hits with exit 0, never an error; `-c nosuch` exits 1 with `Collection not found:
nosuch`; with a bare PATH the launcher exits 127 and through `/usr/bin/env PATH=...` it
answers; `--index nosuchindex` answers `[]` with exit 0 **and creates an empty index**
(`nosuchindex.sqlite` and `.yml`, removed afterwards); `qmd get <absolute path>` reads an
indexed note and prints its URI and docid on its first line. The ripgrep command above
answered NUL-separated paths with exit 0, 1 for no match and 2 with a stderr line for a
missing folder.

### Assumed, for the owner to confirm

- The status keyword is `search`, as the vault's is `vault`.
- `deadline` defaults to 1.0 s, about four times qmd's warm search here; a cold one on the
  Mac (after sleep, the index not in memory) is unmeasured.
- Merging by rank, providers interleaved and config order breaking ties, with no weights.
- `min_chars` 2, the 10 s cache and the 30 s rest after three timeouts are guesses.
- Problem rows go after the hits, so a failure on a long list may sit below the fold.
- The `open` template and its Obsidian example: that `obsidian://open?path=` takes an
  absolute path percent-encoded but for `/` is unverified until the Mac.
- Copy docid only where qmd gives one; Copy path serves the rest.
- With `index` unset, qmd looks for a `.qmd/index.yml` above its working directory (the
  plugin's directory) before its default index; nobody is expected to have one there.
- A misspelt `index` silently searches a new empty index; the plugin cannot tell without
  reading qmd's cache, so the user page warns of it and the no-hits row names the index
  when one is set.
- Two paths that differ only in case, on a case-insensitive disk, are not collapsed.

## Consequences

- Task 3.2 builds this: both kinds, `mode = "search"`, the merging, the cache, the rest,
  the status keyword and the rows, with the tests above. Its user page owes the schema,
  both examples, the PATH rule and the `index` warning.
- Decision 9's provider rule should say it is for feed providers (draft 8), and that a
  search provider runs in `query` under this decision; amending decision 9 is for whoever
  closes this one.
- The command kind takes its query as arguments and prints hits, unlike draft 8's request
  on stdin: a search tool already takes its text as an argument, and a JSON request would
  need a wrapper script for every tool, which is the code task 3 wants to avoid.
- Draft 5: once the host names the `keywords` capability, the plugin sends its keywords
  and drops its own matching. Until then a keyword in both the vault's and this config is
  answered by both plugins, and neither can tell; draft 5 reports such clashes.
- Task 3's open question on the slow modes is answered no, until the four conditions hold.
- The spike's note that qmd's score is "normalised per result set" is corrected above: it
  is a fixed function of BM25, which itself follows the corpus.
