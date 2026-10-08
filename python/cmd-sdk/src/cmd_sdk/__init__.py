"""Write cmd plugins in Python.

A plugin is data and two functions. ``serve`` speaks the protocol for it.
"""

from cmd_sdk.cache import TtlCache
from cmd_sdk.calls import CallResult, call
from cmd_sdk.environment import config, data_dir
from cmd_sdk.locate import ConfigError, MissingVariableError
from cmd_sdk.protocol import (
    PROTOCOL,
    Action,
    Agreement,
    Close,
    Copy,
    Description,
    Effect,
    Icon,
    Item,
    Open,
    PathIcon,
    Plugin,
    Show,
    SymbolIcon,
)
from cmd_sdk.serve import serve

__all__ = [
    "PROTOCOL",
    "Action",
    "Agreement",
    "CallResult",
    "Close",
    "ConfigError",
    "Copy",
    "Description",
    "Effect",
    "Icon",
    "Item",
    "MissingVariableError",
    "Open",
    "PathIcon",
    "Plugin",
    "Show",
    "SymbolIcon",
    "TtlCache",
    "call",
    "config",
    "data_dir",
    "serve",
]
