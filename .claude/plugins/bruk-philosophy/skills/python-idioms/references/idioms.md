# Python Idioms

Every choice in code tells the reader something. This is the list of choices I make in Python and what each one says. Version tags mark the minimum Python needed; untagged entries assume 3.12 or later. When an idiom makes code harder to read, change, or ship, drop the idiom.

## Data

**Frozen dataclass** is the default record. It declares the shape of the data and promises the data will not change, and the type checker keeps the promise. To change a value, make a copy with the change: `dataclasses.replace`, or `copy.replace` (3.13).

**NamedTuple** is a record that also unpacks and indexes. Use it only when positional access is part of the interface. Otherwise the frozen dataclass says more.

**Enum** declares a closed set of choices. Use **StrEnum** when the values leave the program as strings (config keys, wire formats), so members compare equal to their strings.

**TypedDict** declares the shape of a dict that crosses a boundary, such as JSON in or out. `Required` and `NotRequired` mark which keys must be present, `ReadOnly` (3.13) marks keys that must not be written, and `closed=True` (3.15) says no other keys exist. Use `closed=True` in new code so the shape says what is absent as well as what is present.

**frozendict** (3.15) is the immutable mapping. Before 3.15, annotate with `Mapping`, which promises nothing at runtime. frozendict keeps the promise.

**sentinel** (3.15) is how to create our own sentinels. `MISSING = sentinel("MISSING")` makes a unique value with its own name, compared with `is`. Defining one says a state needs a value of its own, such as an argument that was not given where None is a real value. Before 3.15, use a module-private `_MISSING = object()` with a comment.

**The class keyword** appears in four declared forms, dataclass for shape, `Protocol` for contracts, Enum for closed sets, and Exception subclasses for failure, and almost nowhere else. Behaviour lives in functions. A bare class that bundles state with methods is the last resort, so writing one is a loud statement: an invariant must hold while the state changes, or a resource has a lifecycle worth guarding. Inheritance does not appear in the code that holds the logic. It claims one thing is a kind of another, and few designs truly have that relationship.

## Containers and iteration

**list** says the data will change. **tuple** says it will not. A list holding data that nothing changes is a false signal.

**Comprehension** says the whole sequence is needed now. **Generator** says it is not. The same test picks between them every time. A full list built only to feed a single `sum()` is a small lie.

**itertools.batched** (3.12) for splitting into chunks, and unpacking in comprehensions (3.15), `[*chunk for chunk in chunks]`, for flattening. Both replace hand-written loops whose purpose a reader must work out.

## Control flow

**match** declares the shape of data. **if** declares a condition. Use match when the subject is a closed set of shapes, an enum or a union of frozen dataclasses, and end every match with `assert_never`, so the type checker fails any match that misses a case when the set grows:

```python
match event:
    case Purchase(): ...
    case Refund(): ...
    case _ as unreachable:
        assert_never(unreachable)
```

Patterns are literals, dotted names, or class patterns. Never a bare name: `case pending:` captures whatever arrives into `pending` instead of comparing against it. A match over string constants, where if/elif would read plainer, is decoration.

**Exceptions** are for exceptional situations, never for ordinary control flow. Every exception a function raises is listed in its docstring, and a lint rule can check that the list matches the code. At the edges of the program, `Exception.add_note` (3.11) attaches context to an exception in flight without wrapping it, so the type that crosses stays the type that was documented. `except*` belongs only with TaskGroup code.

## Functions and names

**Functions take data and return data.** A function that takes what it needs as arguments, returns a result, and changes nothing else is cheap to test, easy to combine, and rarely meets failure. Reading files, calling networks, and writing databases happen at the edges of the program, not in the code that holds the logic. The purer the logic, the thinner the edges.

**Private by default.** A name without a leading underscore claims it has callers elsewhere. Grant the claim only when a caller exists.

**Generics** use the 3.12 syntax, `def first[T](items: Sequence[T]) -> T`, and the `type` statement for aliases. `TypeVar` is legacy at this floor.

**Self** (3.11) for methods that return their own instance. **TypeIs** (3.13) for functions that narrow a type; it narrows in both branches and replaces most uses of `TypeGuard`.

**`from __future__ import annotations`** goes away at 3.14. Deferred evaluation is the default there, and the import is noise.

## Core and shell

**Return what happens next as a value.** A function takes plain data and hands back what should happen next. One thin function on the outside does the I/O and acts on whatever came back. The inner function says the logic is all here and none of it can touch the outside world. The outer function says it is the only place that can. I think of it as pure core, thin shell, and it is the functional core and imperative shell at the size of a single function.

The value is an Enum when the next steps are a closed set of names, and a union of frozen dataclasses when a step carries data. The shell matches on it and ends with `assert_never`.

```python
class Step(Enum):
    DONE = auto()
    REFRESH_AUTH = auto()
    RETRY = auto()
    FAIL = auto()


def next_step(status: int, attempt: int) -> Step:
    if 200 <= status < 300:
        return Step.DONE
    if status == 401 and attempt == 1:
        return Step.REFRESH_AUTH
    if status >= 500 and attempt < 3:
        return Step.RETRY
    return Step.FAIL


def backoff_s(attempt: int) -> float:
    return 0.2 * 2.0**attempt


def send_with_retry(request: Request) -> Response:
    """Send a request, refreshing auth once and retrying server errors.

    Raises:
        HttpError: The last response was not a success.
    """
    attempt = 1
    while True:
        response = send(request)
        match next_step(response.status, attempt):
            case Step.DONE:
                return response
            case Step.REFRESH_AUTH:
                refresh_token()
            case Step.RETRY:
                time.sleep(backoff_s(attempt))
            case Step.FAIL:
                raise HttpError(response.status)
            case _ as unreachable:
                assert_never(unreachable)
        attempt += 1
```

`next_step` and `backoff_s` are all the logic, and neither one can do I/O. `send_with_retry` is the only thing that touches the network, the token, or the clock. The logic is testable from the start, with plain inputs and no mocks, so testing a branch is one line that passes in two numbers:

```python
assert next_step(503, 1) is Step.RETRY
assert next_step(503, 3) is Step.FAIL
assert next_step(401, 1) is Step.REFRESH_AUTH
assert next_step(401, 2) is Step.FAIL
```

The blast radius stays small as well, because that one outer function is the only thing that can reach the network or the database. Written the usual way, with the logic and the I/O mixed in one function, testing a branch means faking the network, the token refresh, and the clock, and changing the retry rules means editing the same function that makes the calls.

I think some of this comes from Elixir, where the return value would be an atom such as `:retry` or `:fail` and the caller would pattern match on it. The Enum and `match` are the Python version of that.

**A generator that yields its effects** is for logic and I/O that alternate many times, where returning one step at a time would turn the shell into a state machine. The generator yields a description of each effect, the shell performs it and sends the result back in, and the logic still reads top to bottom. This is how sans-IO libraries work. It costs more than returning a step: the reply has one type at every `yield`, the result arrives inside `StopIteration`, a test has to spell out the whole order of effects, and every helper that performs an effect becomes a generator too. Return a step until the shell needs a state machine. The retry handler written this way is in `yielded-effects.md`.

## Strings

**f-string** says the text is finished. **t-string** (3.14) says this is a template that someone must process: the inserted values arrive as data, so SQL, HTML, and shell consumers can escape them properly. Where a function accepts a t-string, a plain string can be refused by type, which makes injection a type error.

## Imports

**lazy import** (3.15) at a program's entry points says a dependency is deferred and startup does not pay for it. Before using it in a module, confirm the module has no side effects at load time.

## Tools

The idioms above are promises. These four tools keep them, and a project that follows this file uses all four.

**uv** is the only way to run Python, install packages, and manage environments. Single-file scripts declare their dependencies inline (PEP 723) and run with `uv run`.

**ruff** formats and lints every file. The docstring rules (DOC501, DOC502) are on, so the exceptions a function lists in its docstring match the exceptions it raises.

**mypy** runs in strict mode over the whole project through a single `typecheck` command, in CI rather than on every edit. It is what turns frozen dataclasses, closed TypedDicts, and `assert_never` from comments into checked promises.

**pypeeker** is my architecture linter. Its `[tool.pypeeker]` import-boundaries table in pyproject.toml records which packages may import which, so the line between the logic and the edges is checked on every run. Run it as `pypeeker check --strict`; plain `check` hides the heuristic findings.
