# philosophy

How I build software, as one Claude Code plugin.

## Install

Put this folder somewhere permanent, then:

```sh
claude plugin marketplace add /path/to/bruk-philosophy
claude plugin install philosophy@bruk-philosophy
```

The same two steps work inside Claude Code as `/plugin marketplace add ...` and
`/plugin install philosophy@bruk-philosophy`. Start a new session afterwards.

The hook runs under `python3` and needs nothing installed. It is written for Python 3.9
and later.

## What it does

| Piece | What it carries | When it reaches the model |
|---|---|---|
| `constraints.md` | The constraints that apply everywhere | Every session, printed by the hook |
| `rules/python.md` | Python dialect, the 3.15 floor, uv, ruff, mypy, pypeeker | First time a `.py` or `pyproject.toml` is touched, in owner mode |
| `rules/python-tests.md` | The four test layers and fakes | First time a Python test file is touched, in owner mode |
| `rules/agent-tooling.md` | Deterministic execution, which primitive carries what | First time a Claude Code extension file is touched |
| `philosophy:work-loop` | How we work, the board, intents, the model table | On demand |
| `philosophy:python-idioms` | The full idiom dictionary and the yielded-effects example | On demand |
| `docs/engineering-philosophy.md` | The reasoning | Never; the constraints point at it |

Claude Code does not load a plugin's `CLAUDE.md` or `rules/`, so `hooks/context.py` does
that job. A rule arrives once per session, and again after a compact or a clear.

## Owner mode and guest mode

The hook decides the mode from the repository's git origin and says which one applies
on the first line of every session.

- **Owner:** the origin matches a line in `owners.txt`, or the repository has no origin.
- **Guest:** everything else. The two Python rules are not loaded.

Edit `owners.txt` to add an organisation or a single repository.

## Tests

```sh
uv run --with pytest pytest tests
```

The tests cover the hook's logic and run it as a subprocess against throwaway
repositories. To run the hook under a specific interpreter, set `HOOK_PYTHON`.

`claude plugin validate --strict .` checks the manifests and the hook config.

## What it does not do

- **It enforces nothing.** These are constraints the model reads. The uv guard, ruff
  and ast-grep on edit, and the read-only reviewer agent live in the `bruk` and `idiom`
  plugins. Much of `rules/python.md` could be lint rules, and here it is prose.
- **Parts of `work-loop` are untried.** Intents as root tasks, the accept step, and
  `references/board-frontmatter.md` have not been used on real work.
- **It overlaps the `bruk` and `idiom` plugins.** With those enabled as well, the same
  ground is covered twice in different words. Use one or the other.

## Remove

```sh
claude plugin uninstall philosophy@bruk-philosophy
claude plugin marketplace remove bruk-philosophy
```
