---
paths:
  - "**/*.py"
  - "**/pyproject.toml"
mode: owner
---
# Python

Applies when reading or writing Python in a repository I own.

When a line here makes the code harder to read, harder to change, or harder to ship,
drop it. Every construct below declares something to the reader, and the declaration
must be true. A tag such as (3.15) is the minimum Python the construct needs, so check
the project's `requires-python`. The `philosophy:python-idioms` skill holds the full
dictionary, including the forms to use on earlier versions.

## Floor and tools

- Python 3.15 is the floor for my own projects, including before it reaches final.
- uv is the only way to run Python, install packages, and manage environments.
  Single-file scripts declare their dependencies inline (PEP 723) and run with `uv run`.
- ruff formats and lints, with DOC501 and DOC502 on. Both need ruff's preview mode, and
  without it ruff ignores them.
- mypy runs in strict mode behind a single `typecheck` command, gated in CI. It does not
  run on every edit.
- pypeeker enforces the import boundaries declared in `[tool.pypeeker]`. Run
  `pypeeker check --strict`, because plain `check` hides the heuristic findings.
- pytest runs against a `src/` layout.
- A multi-package repository is a uv workspace: the root is not a package, there is one
  lock and one venv, and shared config lives at the root. pytest then needs
  `--import-mode=importlib` together with `consider_namespace_packages = true`, and
  strict mypy needs `explicit_package_bases` with a `mypy_path` that lists every
  member's `src/`.

## Shape of the code

- Functional core, imperative shell. The logic takes data and returns data. Reading
  files, calling networks, and writing databases happen at the edges, and the import
  contract keeps them out of the core.
- Pure core, thin shell at the size of a function: the logic takes plain data and hands
  back what should happen next as a value, and one thin function on the outside does
  the I/O and acts on it. That outer function is the only thing that touches the
  network, the database, or the clock.
- Determinism enters the core as data, through parameters such as `now` and `rng`. It
  never enters by patching.
- The `class` keyword appears in four declared forms and almost nowhere else: dataclass
  for shape, `Protocol` for contracts, Enum for closed sets, and Exception subclasses
  for failure. Behaviour lives in functions.
- A bare class that bundles state with methods is the last resort. Write one only when
  an invariant must hold while the state changes, or a resource has a lifecycle worth
  guarding.
- No inheritance in the code that holds the logic.
- Private by default. A name loses its leading underscore only when a caller exists
  elsewhere.
- `__init__.py` holds imports and `__all__` only. Behaviour lives in named modules.

## Data

- A frozen dataclass is the default record. Use a NamedTuple only when positional access
  is part of the interface.
- The value that says what happens next is an Enum when the steps are a closed set of
  names, or a StrEnum when it crosses the wire. Steps that carry data are a union of
  frozen dataclasses or NamedTuples. The shell matches on it.
- A TypedDict declares a dict that crosses a boundary. Use `closed=True` (3.15) in new
  code.
- `frozendict` (3.15) is the immutable mapping.
- `sentinel` (3.15) creates our own named sentinels. Define one when a state needs a
  value of its own and None is a real value.
- `list` says the data will change and `tuple` says it will not. A comprehension says
  the whole sequence is needed now and a generator says it is not.

## Control flow and errors

- `match` declares the shape of data and `if` declares a condition. Use `match` on a
  closed set of shapes and end it with `assert_never`.
- Match patterns are literals, dotted names, or class patterns. A bare name captures
  instead of comparing, so never use one.
- Exceptions are for exceptional situations, never for ordinary control flow. Raise
  natively; do not return Result types.
- Every exception a function raises is listed in its docstring.
- At the edges, attach context with `Exception.add_note` so the documented type is the
  type that crosses. `except*` belongs only with TaskGroup code.

## Syntax at the floor

- Generics use the 3.12 syntax and the `type` statement. `TypeVar` is legacy.
- `from __future__ import annotations` goes away at 3.14.
- An f-string says the text is finished. A t-string (3.14) says it is a template that
  someone must process. A function that accepts a t-string can refuse a plain string by
  type.
- `lazy import` (3.15) belongs at a program's entry points. Confirm the module has no
  side effects at load time before using it.
