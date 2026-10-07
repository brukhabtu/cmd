# Writing a plugin

A plugin is a directory with three things in it: a `cmd-plugin.toml` that says how to start
it, a `pyproject.toml` that depends on `cmd-sdk`, and a Python package with two functions:
one turns the text the person typed into rows, the other says what happens when they pick
one. cmd starts the plugin as its own process and talks to it in
[JSON lines](../plugin-protocol.md); the SDK does the talking, so a plugin is the two
functions and little else.

```python
from cmd_sdk import Copy, Description, Effect, Item, Plugin


def query(text: str) -> list[Item]:
    return [Item(id=text, title=text.upper())]


def run(item: str, action: str) -> Effect:
    return Copy(item.upper())


PLUGIN = Plugin(Description(name="shout", version="0.1.0"), query, run)
```

- [Tutorial](tutorial.md): a working plugin, from an empty directory, in ten minutes.
- [The protocol](../plugin-protocol.md): what the SDK says on your behalf, for when you
  want to know or write a plugin in another language.
- [Example plugins](examples.md): the plugins in this repository, each a small complete
  example.
- [Testing](testing.md) and [publishing](publishing.md) a plugin.
- [SDK reference](../reference/python/index.md): every class and function, generated from
  the code.
