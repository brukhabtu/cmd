"""The pure half of the environment helpers: what a variable or a TOML text means.

Nothing here reads the environment or the file system; ``environment`` does, and passes
the values in.
"""

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DATA_VARIABLE = "CMD_PLUGIN_DATA"
CONFIG_VARIABLE = "CMD_PLUGIN_CONFIG"
CONFIG_FILE = "config.toml"


class MissingVariableError(RuntimeError):
    """A variable the host should have set is missing or empty. The message names it."""


class ConfigError(ValueError):
    """A plugin's config file is not valid TOML. The message names the file and the problem."""


def directory_from(environ: Mapping[str, str], variable: str) -> Path:
    """The directory named by ``variable``, or ``MissingVariableError`` if it has none.

    Raises:
        MissingVariableError: the variable is missing or empty.
    """
    value = environ.get(variable, "")
    if not value.strip():
        raise MissingVariableError(
            f"{variable} is not set; the cmd host sets it for each plugin it starts"
        )
    return Path(value)


def parse_config(text: str, source: Path) -> dict[str, Any]:
    """The TOML table in ``text``; ``source`` is only named in the error.

    Raises:
        ConfigError: the text is not valid TOML.
    """
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{source} is not valid TOML: {error}") from error
