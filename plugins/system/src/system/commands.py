"""The commands, and which typed text names each one.

All data and matching, no I/O. A command is a row for the list and one fixed argv that
performs it. The paths are absolute on purpose: an app launched from the Dock has
launchd's PATH, not the shell's, and these binaries sit where SIP keeps them, so a bare
name would buy nothing and could resolve to something else first.
"""

from dataclasses import dataclass

MIN_PREFIX = 2
"""The shortest text that names a command.

A definite item outranks every fuzzy one, so a single letter would put Sleep above Safari.
"""


@dataclass(frozen=True)
class Command:
    """One thing the plugin can do: how it is listed, what names it, what performs it."""

    id: str
    title: str
    subtitle: str
    names: tuple[str, ...]
    argv: tuple[str, ...]


SLEEP = Command(
    "sleep",
    "Sleep",
    "Puts the Mac to sleep",
    ("sleep",),
    ("/usr/bin/pmset", "sleepnow"),
)

LOCK = Command(
    "lock",
    "Lock screen",
    "Locks the screen",
    ("lock", "lock screen", "screen"),
    ("/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"),
)

EMPTY_TRASH = Command(
    "empty-trash",
    "Empty Trash",
    "Empties the Trash in Finder",
    ("empty trash", "trash", "empty"),
    ("/usr/bin/osascript", "-e", 'tell application "Finder" to empty trash'),
)

DARK_MODE = Command(
    "dark-mode",
    "Toggle dark mode",
    "Switches between light and dark appearance",
    ("dark mode", "dark", "light mode", "light", "appearance", "toggle dark mode"),
    (
        "/usr/bin/osascript",
        "-e",
        (
            'tell application "System Events" to tell appearance preferences'
            " to set dark mode to not dark mode"
        ),
    ),
)

COMMANDS = (SLEEP, LOCK, EMPTY_TRASH, DARK_MODE)


def matching(text: str) -> tuple[Command, ...]:
    """The commands one of whose names starts with ``text``, in table order.

    Case and runs of whitespace do not count; text shorter than ``MIN_PREFIX`` names
    nothing.
    """
    needle = " ".join(text.lower().split())
    if len(needle) < MIN_PREFIX:
        return ()
    return tuple(
        command for command in COMMANDS if any(name.startswith(needle) for name in command.names)
    )


def by_id(item: str) -> Command | None:
    """The command with this id, or ``None`` for an id this plugin never issued."""
    return next((command for command in COMMANDS if command.id == item), None)
