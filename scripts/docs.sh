#!/usr/bin/env bash
# Build the documentation site into site/. rustdoc runs first, so the Rust API reference
# is in it; then MkDocs, strict, so a broken link, a missing page or a reference the
# generators could not resolve fails the build instead of shipping. Extra arguments go to
# mkdocs build (for example --site-dir).
set -euo pipefail
cd "$(dirname "$0")/.."

# rustdoc merges its crate list and search index into whatever an earlier run left in
# target/doc, so the reference starts from an empty one. --lib leaves out cmd-host's
# cmd-plugin binary, whose pages the site does not carry.
cargo clean --doc
# Warnings are errors here too: a broken intra-doc link is a broken page in the site.
RUSTDOCFLAGS="${RUSTDOCFLAGS:-} -D warnings" cargo doc --no-deps --lib -p cmd-core -p cmd-host
uv run --group docs mkdocs build --strict "$@"
