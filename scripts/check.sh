#!/usr/bin/env bash
# Everything CI runs, in one place, so a contributor runs the same checks locally.
# Each step says what it checks; a failure prints the tool's own message.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s\n' "$*"; }

step "rust: formatting"
cargo fmt --all --check

step "rust: clippy on the crates that build everywhere"
cargo clippy --workspace --exclude cmd-app --all-targets -- -D warnings

step "rust: tests, including the adapter test that runs the calculator plugin through uv"
uv sync --all-packages --all-groups --quiet
cargo test --workspace --exclude cmd-app

if [[ "$(uname)" == "Darwin" ]]; then
  step "rust: the GPUI app (macOS only; Linux hits an xattr/libc clash below GPUI)"
  cargo clippy -p cmd-app -- -D warnings
fi

step "python: ruff format and lint"
uv run ruff format --check .
uv run ruff check .

step "python: mypy strict"
uv run mypy

step "python: pytest"
uv run pytest -q

step "python: the functional suite twice in one process, to catch state leakage"
uv run pytest -q --keep-duplicates python/cmd-sdk/tests/functional python/cmd-sdk/tests/functional

# pypeeker is configured in pyproject.toml but not gated here: at the pinned commit its
# import-boundaries rule cannot see an import that crosses the two source roots, so a passing
# check would prove nothing. Board task "Make the SDK/plugin and core/shell import boundaries
# mechanical" owns closing that gap.

step "claude code: plugin manifests"
claude plugin validate --strict .claude/plugins/bruk-philosophy
claude plugin validate --strict .claude/plugins/cmd-dev

step "claude code: the philosophy hook's own tests"
uv run pytest -q -p no:cacheprovider -c /dev/null --rootdir=.claude/plugins/bruk-philosophy .claude/plugins/bruk-philosophy/tests

printf '\nall checks passed\n'
