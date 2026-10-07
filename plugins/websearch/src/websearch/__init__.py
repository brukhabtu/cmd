"""Search the web from the launcher: ``web <question>`` opens a search for it.

The tutorial plugin. It shows the three things a plugin can do beyond answering: own a
keyword, offer more than one action, and ask the host to open something.
"""

from urllib.parse import quote_plus

from cmd_sdk import (
    Action,
    Copy,
    Description,
    Effect,
    Item,
    Open,
    Plugin,
    Show,
    SymbolIcon,
    serve,
)
from cmd_sdk.protocol import DEFAULT_ACTION

_ENGINE = "https://duckduckgo.com/?q="
_OPEN = "open"
_COPY = "copy"
_ICON = SymbolIcon("globe")


def search_url(question: str) -> str:
    """The search page for a question, with the question made safe for a URL."""
    return _ENGINE + quote_plus(question.strip())


def _query(text: str) -> tuple[Item, ...]:
    question = text.strip()
    if not question:
        return (
            Item(id="", title="Search the web", subtitle="Type a question after 'web'", icon=_ICON),
        )
    return (
        Item(
            id=search_url(question),
            title=f"Search the web for {question!r}",
            subtitle="Enter opens the search, the second action copies its address",
            actions=(Action(_OPEN, "Open the search"), Action(_COPY, "Copy the address")),
            icon=_ICON,
        ),
    )


def _run(item: str, action: str) -> Effect:
    if not item:
        return Show(text="Type a question after 'web' first")
    if action in {DEFAULT_ACTION, _OPEN}:
        return Open(target=item)
    if action == _COPY:
        return Copy(text=item)
    return Show(text=f"websearch has no action {action!r}")


PLUGIN = Plugin(Description(name="websearch", version="0.1.0", keyword="web"), _query, _run)


def main() -> None:
    """Serve the plugin over stdin and stdout."""
    serve(PLUGIN)
