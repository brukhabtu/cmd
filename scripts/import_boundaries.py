# /// script
# requires-python = ">=3.12"
# ///
"""Fail when an import crosses a line the architecture draws between source roots.

The SDK knows no plugin, and no plugin knows another: `cmd_sdk` must not import a package
that lives under a plugin's source root, and a plugin package must not import a sibling.
pypeeker gates the lines inside one source root; this gates the lines between roots, which
its rule cannot see. Standard library only, so it runs wherever Python does.

Usage: python scripts/import_boundaries.py <sdk-src-root> <plugin-src-root>...
"""

import ast
import sys
from pathlib import Path


def packages_under(root: Path) -> set[str]:
    """The top-level packages a source root holds: its directories with an `__init__.py`."""
    return {child.name for child in root.iterdir() if (child / "__init__.py").is_file()}


def modules(root: Path) -> list[tuple[str, Path]]:
    """Every module under a source root, with the top-level package it belongs to."""
    return [
        (package, path)
        for package in sorted(packages_under(root))
        for path in sorted((root / package).rglob("*.py"))
    ]


def imported_roots(source: str, path: str) -> list[tuple[int, str]]:
    """Each absolute import in a module, as the line and the top-level package it names."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source, filename=path)):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name.split(".")[0]) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module.split(".")[0]))
    return found


def crossings(sdk_root: Path, plugin_roots: list[Path]) -> list[str]:
    """Every import that crosses a line, as `path:line: <package> imports <package>`."""
    plugin_packages = {package for root in plugin_roots for package in packages_under(root)}
    problems: list[str] = []
    for root in [sdk_root, *plugin_roots]:
        for package, path in modules(root):
            imports = imported_roots(path.read_text(encoding="utf-8"), str(path))
            problems.extend(
                f"{path}:{line}: {package} imports {imported}"
                for line, imported in imports
                if imported in plugin_packages and imported != package
            )
    return problems


_USAGE_ERROR = 2


def main(argv: list[str]) -> int:
    """Print each crossing, then the verdict as the exit code."""
    match argv:
        case [_, sdk_root, *plugin_roots] if plugin_roots:
            problems = crossings(Path(sdk_root), [Path(root) for root in plugin_roots])
        case _:
            print(__doc__, file=sys.stderr)
            return _USAGE_ERROR
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
