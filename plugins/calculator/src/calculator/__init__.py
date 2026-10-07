"""Arithmetic in the launcher. No keyword: it answers whenever the text is an expression."""

from cmd_sdk import Copy, Description, Effect, Item, Plugin, Show, serve
from cmd_sdk.protocol import DEFAULT_ACTION

from calculator.arithmetic import evaluate, render

_COPY = "copy"


def _query(text: str) -> tuple[Item, ...]:
    value = evaluate(text)
    if value is None:
        return ()
    shown = render(value)
    return (Item(id=shown, title=shown, subtitle="Press Enter to copy"),)


def _run(item: str, action: str) -> Effect:
    if action in {DEFAULT_ACTION, _COPY}:
        return Copy(text=item)
    return Show(text=f"calculator has no action {action!r}")


PLUGIN = Plugin(Description(name="calculator", version="0.1.0"), _query, _run)


def main() -> None:
    """Serve the plugin over stdin and stdout."""
    serve(PLUGIN)
