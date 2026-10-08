from pathlib import Path

import pytest
from cmd_sdk import ConfigError, MissingVariableError, config, data_dir


def test_data_dir_is_the_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CMD_PLUGIN_DATA", str(tmp_path))
    assert data_dir() == tmp_path


@pytest.mark.parametrize("value", [None, ""])
def test_data_dir_without_the_variable_names_it(
    value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value is None:
        monkeypatch.delenv("CMD_PLUGIN_DATA", raising=False)
    else:
        monkeypatch.setenv("CMD_PLUGIN_DATA", value)
    with pytest.raises(MissingVariableError, match="CMD_PLUGIN_DATA"):
        data_dir()


def test_config_reads_config_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.toml").write_text('vault = "/v"\n[cli]\ntimeout = 2\n')
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(tmp_path))
    assert config() == {"vault": "/v", "cli": {"timeout": 2}}


def test_config_with_no_directory_or_no_file_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(tmp_path / "absent"))
    assert config() == {}
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(tmp_path))
    assert config() == {}


def test_config_that_is_not_toml_names_file_and_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.toml").write_text("not = = toml")
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(tmp_path))
    with pytest.raises(ConfigError, match=r"config\.toml is not valid TOML: "):
        config()


def test_config_that_is_not_text_is_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.toml").write_bytes(b"\xff\xfe\x00")
    monkeypatch.setenv("CMD_PLUGIN_CONFIG", str(tmp_path))
    with pytest.raises(ConfigError, match=r"config\.toml"):
        config()


def test_config_without_the_variable_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CMD_PLUGIN_CONFIG", raising=False)
    with pytest.raises(MissingVariableError, match="CMD_PLUGIN_CONFIG"):
        config()
