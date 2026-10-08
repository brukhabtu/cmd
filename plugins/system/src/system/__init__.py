"""What the Mac does on command: sleep, lock the screen, empty the Trash, toggle dark mode.

No keyword. Type a command's name and it is the first row, because a command is a definite
answer and the host ranks those above every fuzzy match. Enter performs it and the
launcher hides.
"""

import sys
from collections.abc import Callable, Sequence

from cmd_sdk import Close, Description, Effect, Item, Plugin, Show, SymbolIcon, call, serve
from cmd_sdk.protocol import DEFAULT_ACTION

from system.commands import by_id, matching

type Executor = Callable[[Sequence[str]], str | None]
"""Runs one command's argv and says what went wrong, or ``None`` when nothing did."""

PATIENCE = 2.0
"""Seconds to wait for a command before answering anyway.

Well inside the host's deadline for ``run``. Finder and System Events put up a one-time
Automation consent prompt that outlasts any sensible wait, and the launcher should be out
of the way while the person answers it, so a command still running after this long counts
as having worked.
"""


def execute(argv: Sequence[str], patience: float = PATIENCE) -> str | None:
    """Run ``argv`` and return its failure as one line, or ``None`` when it succeeded.

    A command still running after ``patience`` seconds is left to finish on its own (see
    ``PATIENCE``); ``cmd_sdk.call`` starts it in a session of its own so it outlives this
    process too.
    """
    try:
        result = call(argv, patience)
    except OSError as error:
        return f"{argv[0]}: {error.strerror}"
    if result.timed_out or result.returncode == 0:
        return None
    stderr = result.stderr.decode("utf-8", errors="replace")
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else f"{argv[0]} exited with {result.returncode}"


def plugin(execute: Executor = execute, platform: str = sys.platform) -> Plugin:
    """The plugin with its executor and platform fixed, so a test can fake both."""

    def _query(text: str) -> tuple[Item, ...]:
        return tuple(
            Item(
                id=command.id,
                title=command.title,
                subtitle=command.subtitle,
                icon=SymbolIcon(command.symbol),
            )
            for command in matching(text)
        )

    def _run(item: str, action: str) -> Effect:
        command = by_id(item)
        if command is None:
            return Show(text=f"system has no command {item!r}")
        if action != DEFAULT_ACTION:
            return Show(text=f"system has no action {action!r}")
        if platform != "darwin":
            return Show(text=f"{command.title} needs macOS")
        failure = execute(command.argv)
        if failure is not None:
            return Show(text=f"{command.title}: {failure}")
        return Close()

    return Plugin(Description(name="system", version="0.1.0"), _query, _run)


PLUGIN = plugin()


def main() -> None:
    """Serve the plugin over stdin and stdout."""
    serve(PLUGIN)
