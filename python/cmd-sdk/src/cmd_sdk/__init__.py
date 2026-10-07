"""Write cmd plugins in Python.

A plugin is data and two functions. ``serve`` speaks the protocol for it.
"""

from cmd_sdk.protocol import (
    PROTOCOL,
    Action,
    Close,
    Copy,
    Description,
    Effect,
    Item,
    Open,
    Plugin,
    Show,
)
from cmd_sdk.serve import serve

__all__ = [
    "PROTOCOL",
    "Action",
    "Close",
    "Copy",
    "Description",
    "Effect",
    "Item",
    "Open",
    "Plugin",
    "Show",
    "serve",
]
