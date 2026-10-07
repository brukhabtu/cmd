#!/usr/bin/env bash
# Build the documentation site into site/. rustdoc runs first, so the Rust API reference
# is in it; then MkDocs, strict, so a broken link, a missing page or a reference the
# generators could not resolve fails the build instead of shipping. Extra arguments go to
# mkdocs build (for example --site-dir).
set -euo pipefail
cd "$(dirname "$0")/.."

# Warnings are errors here too: a broken intra-doc link is a broken page in the site.
RUSTDOCFLAGS="${RUSTDOCFLAGS:-} -D warnings" cargo doc --no-deps -p cmd-core -p cmd-host
uv run --group docs mkdocs build --strict "$@"
