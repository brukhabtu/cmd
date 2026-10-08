from pathlib import Path

import pytest
from cmd_sdk.expiry import expired
from cmd_sdk.locate import ConfigError, MissingVariableError, directory_from, parse_config


def test_a_set_variable_gives_its_path() -> None:
    assert directory_from({"X": "/some/where"}, "X") == Path("/some/where")


@pytest.mark.parametrize("environ", [{}, {"CMD_PLUGIN_DATA": ""}, {"CMD_PLUGIN_DATA": "  "}])
def test_a_missing_or_empty_variable_is_named(environ: dict[str, str]) -> None:
    with pytest.raises(MissingVariableError, match="CMD_PLUGIN_DATA"):
        directory_from(environ, "CMD_PLUGIN_DATA")


def test_toml_becomes_a_dict() -> None:
    assert parse_config('a = 1\n[t]\nb = "x"\n', Path("c.toml")) == {"a": 1, "t": {"b": "x"}}


def test_bad_toml_names_the_file_and_the_problem() -> None:
    with pytest.raises(ConfigError, match=r"/etc/p/config\.toml is not valid TOML: .+"):
        parse_config("a = = 1", Path("/etc/p/config.toml"))


def test_expiry() -> None:
    assert expired(0.0, None, 10)
    assert not expired(5.0, 0.0, 10)
    assert expired(10.0, 0.0, 10)
    assert expired(1.0, 5.0, 10)  # the clock went backwards
