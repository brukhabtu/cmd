"""The watchdemo plugin: watch fake tickets in a local JSON file (decision 13).

``watch`` and some text finds tickets in the file named by ``tickets`` in ``config.toml``;
Watch on one, and a thread that reads the file every few seconds tells the host when its
status moves. ``watchdemo.plugin`` is the shell; ``tickets``, ``options``, ``state``,
``diff`` and ``rows`` are the pure core, and ``keeper`` and ``poller`` the file and thread
shells.
"""

from watchdemo.plugin import main

__all__ = ["main"]
