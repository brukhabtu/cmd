"""The shell half of the environment helpers: where a plugin keeps its data and its config.

The host decides both places and passes them as ``CMD_PLUGIN_DATA`` and
``CMD_PLUGIN_CONFIG``. The SDK never makes a path up.
"""

import os
from pathlib import Path
from typing import Any

from cmd_sdk.locate import (
    CONFIG_FILE,
    CONFIG_VARIABLE,
    DATA_VARIABLE,
    ConfigError,
    directory_from,
    parse_config,
)


def data_dir() -> Path:
    """The plugin's data directory: the absolute path in ``CMD_PLUGIN_DATA``.

    The host creates it. Raises ``MissingVariableError`` naming the variable when it is
    missing or empty.
    """
    return directory_from(os.environ, DATA_VARIABLE)


def config() -> dict[str, Any]:
    """The plugin's settings: ``config.toml`` in the directory named by ``CMD_PLUGIN_CONFIG``.

    The host does not create that directory, so a missing directory or file is an empty
    dict. A file that cannot be read as TOML raises ``ConfigError`` naming the file and
    the problem; a missing variable raises ``MissingVariableError`` naming it.

    Raises:
        ConfigError: the file is not valid TOML.
    """
    path = directory_from(os.environ, CONFIG_VARIABLE) / CONFIG_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError, NotADirectoryError:
        return {}
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from error
    return parse_config(text, path)
