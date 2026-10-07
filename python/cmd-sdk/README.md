# cmd-sdk

Write a cmd plugin in Python. This page is the ten-minute version; `docs/plugin-protocol.md`
at the root of the repository is the whole contract.

A plugin is a `Plugin`: a `Description`, a `query` function that turns the typed text into
`Item`s, and a `run` function that turns a chosen item and action into an `Effect` the host
performs. `serve(plugin)` speaks the protocol over stdin and stdout.

## A plugin in ten minutes

The subject is `plugins/websearch` in this repository: type `web` and a question, press
Enter, and the search opens in the browser. Three files.

**1. The project.** `pyproject.toml` declares a package, a dependency on `cmd-sdk`, and a
script the launcher will run:

```toml
[project]
name = "websearch"
version = "0.1.0"
requires-python = ">=3.15"
dependencies = ["cmd-sdk"]

[project.scripts]
websearch = "websearch:main"

[build-system]
requires = ["uv_build>=0.9,<1"]
build-backend = "uv_build"
```

(Inside this repository `cmd-sdk` comes from the workspace; outside it, from the package
index once it is published.)

**2. The manifest.** `cmd-plugin.toml` tells the launcher what to run, with the plugin's
directory as the working directory:

```toml
name = "websearch"
command = ["uv", "run", "--quiet", "websearch"]
```

**3. The code.** `src/websearch/__init__.py`:

```python
from urllib.parse import quote_plus

from cmd_sdk import Action, Copy, Description, Effect, Item, Open, Plugin, Show, serve
from cmd_sdk.protocol import DEFAULT_ACTION


def search_url(question: str) -> str:
    return "https://duckduckgo.com/?q=" + quote_plus(question.strip())


def _query(text: str) -> tuple[Item, ...]:
    question = text.strip()
    if not question:
        return (Item(id="", title="Search the web", subtitle="Type a question after 'web'"),)
    return (
        Item(
            id=search_url(question),
            title=f"Search the web for {question!r}",
            actions=(Action("open", "Open the search"), Action("copy", "Copy the address")),
        ),
    )


def _run(item: str, action: str) -> Effect:
    if not item:
        return Show(text="Type a question after 'web' first")
    if action in {DEFAULT_ACTION, "open"}:
        return Open(target=item)
    if action == "copy":
        return Copy(text=item)
    return Show(text=f"websearch has no action {action!r}")


PLUGIN = Plugin(Description(name="websearch", version="0.1.0", keyword="web"), _query, _run)


def main() -> None:
    serve(PLUGIN)
```

What each part declares:

- `keyword="web"` means the plugin sees only text that starts with `web`, with the word
  stripped. Leave the keyword out and the plugin sees everything the person types, like
  the calculator does; then return no items for text that is not yours.
- `query` returns data, never performs anything. The item's `id` is what comes back in
  `run`, so make it carry what `run` needs: here, the URL itself.
- `actions` are what Enter can do; the first is the default. With none, the host sends
  `"default"`.
- `run` returns an `Effect` and the host performs it: `Open` a URL or path, `Copy` text,
  `Show` a line and stay open, or `Close`. A plugin may also do its own work in `run`
  (toggle a setting, say) and then return `Close`.
- Log to stderr. Stdout belongs to the protocol, and the host rejects anything else on it.

**4. Try it without the app.** `cmd-doctor` runs a plugin directory the way the launcher
does and prints what comes back:

```sh
cargo run -p cmd-host --bin cmd-doctor -- plugins/websearch --query "rust gpui" --run "https://duckduckgo.com/?q=rust+gpui" --action copy
```

**5. Install it.** Copy the directory into `~/Library/Application Support/cmd/plugins/`,
or run the app with `CMD_PLUGINS=/path/to/your/plugins`. The launcher starts every plugin
it finds and shows a line under the input if one fails to start.

## Testing a plugin

`query` and `run` are plain functions, so the tests are plain too; see
`plugins/websearch/tests/unit/test_plugin.py`. The SDK's own functional tests show how to
drive `serve` with `StringIO` streams if you need to test the loop.
