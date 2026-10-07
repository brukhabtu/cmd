"""The lines between source roots: the SDK knows no plugin, and no plugin knows another."""

from pathlib import Path

from import_boundaries import crossings

REPOSITORY = Path(__file__).resolve().parents[2]


def package(root: Path, name: str, **modules: str) -> Path:
    """A package under a source root, with the given modules' source."""
    (root / name).mkdir(parents=True)
    (root / name / "__init__.py").write_text("", encoding="utf-8")
    for module, source in modules.items():
        (root / name / f"{module}.py").write_text(source, encoding="utf-8")
    return root


def test_a_clean_tree_has_no_crossings(tmp_path: Path) -> None:
    sdk = package(tmp_path / "sdk", "cmd_sdk", serve="import json\nfrom cmd_sdk import protocol\n")
    calculator = package(tmp_path / "a", "calculator", plugin="from cmd_sdk import Item\n")
    websearch = package(tmp_path / "b", "websearch", plugin="import websearch.urls\n")
    assert crossings(sdk, [calculator, websearch]) == []


def test_the_sdk_importing_a_plugin_is_a_crossing(tmp_path: Path) -> None:
    sdk = package(tmp_path / "sdk", "cmd_sdk", serve="import os\nimport calculator\n")
    calculator = package(tmp_path / "a", "calculator")
    assert crossings(sdk, [calculator]) == [
        f"{sdk / 'cmd_sdk' / 'serve.py'}:2: cmd_sdk imports calculator"
    ]


def test_a_plugin_importing_another_is_a_crossing_and_itself_is_not(tmp_path: Path) -> None:
    sdk = package(tmp_path / "sdk", "cmd_sdk")
    calculator = package(tmp_path / "a", "calculator", plugin="from calculator import arithmetic\n")
    websearch = package(
        tmp_path / "b", "websearch", plugin="from calculator.arithmetic import evaluate\n"
    )
    assert crossings(sdk, [calculator, websearch]) == [
        f"{websearch / 'websearch' / 'plugin.py'}:1: websearch imports calculator"
    ]


def test_relative_imports_and_nested_modules_are_read_as_their_package(tmp_path: Path) -> None:
    sdk = package(tmp_path / "sdk", "cmd_sdk")
    calculator = package(tmp_path / "a", "calculator", plugin="from . import arithmetic\n")
    (calculator / "calculator" / "deep").mkdir()
    (calculator / "calculator" / "deep" / "__init__.py").write_text("", encoding="utf-8")
    (calculator / "calculator" / "deep" / "inner.py").write_text(
        "import websearch\n", encoding="utf-8"
    )
    websearch = package(tmp_path / "b", "websearch")
    assert crossings(sdk, [calculator, websearch]) == [
        f"{calculator / 'calculator' / 'deep' / 'inner.py'}:1: calculator imports websearch"
    ]


def test_the_repository_crosses_no_line() -> None:
    plugin_roots = sorted(REPOSITORY.glob("plugins/*/src"))
    assert plugin_roots, "the plugins have source roots"
    assert crossings(REPOSITORY / "python" / "cmd-sdk" / "src", plugin_roots) == []
