"""The vault plugin: capture into Obsidian and search it, from the launcher (decision 10).

``todo``, ``note`` and every other keyword come from the plugin's ``config.toml``. A capture
goes to an outbox in the data directory and a thread writes it through the obsidian CLI, so
nothing is lost while Obsidian is closed or slow. ``vault.plugin`` is the shell; ``schema``,
``outbox``, ``invocations`` and ``answers`` are the pure core.
"""

from vault.plugin import main

__all__ = ["main"]
