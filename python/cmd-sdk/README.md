# cmd-sdk

Write a cmd plugin in Python.

A plugin is a `Plugin`: a `Description`, a `query` function that turns the typed text into
`Item`s, and a `run` function that turns a chosen item and action into an `Effect` for the
host to perform. `serve(plugin)` speaks the protocol over stdin and stdout. The protocol is
specified in `docs/plugin-protocol.md` at the root of the repository.

```python
from cmd_sdk import Copy, Description, Item, Plugin, serve


def query(text: str) -> tuple[Item, ...]:
    return (Item(id=text.upper(), title=text.upper(), subtitle="Press Enter to copy"),)


def run(item: str, action: str) -> Copy:
    return Copy(text=item)


PLUGIN = Plugin(Description(name="shout", version="0.1.0", keyword="shout"), query, run)

if __name__ == "__main__":
    serve(PLUGIN)
```

Log to stderr. Stdout belongs to the protocol, and the host rejects anything else on it.
