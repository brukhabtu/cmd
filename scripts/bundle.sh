#!/usr/bin/env bash
# Build cmd.app on a Mac (task 1.23): the release binary, the bundle around it from the
# [package.metadata.bundle] table in crates/cmd-app/Cargo.toml, and uv beside the binary
# in Contents/MacOS (decision 7). Then check the result and zip it with ditto, because
# actions/upload-artifact drops the executable bits a directory upload would need.
#
# Needs cargo-bundle 0.12.0 on PATH (`cargo install cargo-bundle --version 0.12.0 --locked`).
# The bundle lands at target/release/bundle/osx/cmd.app, the zip beside it.
set -euo pipefail
cd "$(dirname "$0")/.."

# The one pin for the bundled uv. Move it when a uv release lists Python 3.15.0 final for
# darwin; the listing printed below says which 3.15 this uv would fetch.
UV_VERSION="${UV_VERSION:-0.12.23}"

step() { printf '\n== %s\n' "$*"; }

if [[ "$(uname)" != "Darwin" ]]; then
  echo "bundle.sh builds a macOS bundle and runs on macOS only" >&2
  exit 1
fi

case "$(uname -m)" in
  arm64) triple=aarch64-apple-darwin ;;
  x86_64) triple=x86_64-apple-darwin ;;
  *)
    echo "no uv build for $(uname -m)" >&2
    exit 1
    ;;
esac

step "the release binary"
cargo build --release -p cmd-app

step "the bundle (cargo-bundle's own build has no --package, so it is skipped)"
# cargo-bundle resolves the icon and plist paths from the working directory: the root.
CARGO_BUNDLE_SKIP_BUILD=1 cargo bundle --package cmd-app --release --format osx
app=target/release/bundle/osx/cmd.app

step "uv $UV_VERSION for $triple, checked against its published sha256, into Contents/MacOS"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
base="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$triple.tar.gz"
curl --fail --silent --show-error --location --output "$work/uv.tar.gz" "$base"
curl --fail --silent --show-error --location --output "$work/uv.tar.gz.sha256" "$base.sha256"
want="$(awk '{print $1}' "$work/uv.tar.gz.sha256")"
have="$(shasum -a 256 "$work/uv.tar.gz" | awk '{print $1}')"
if [[ "$want" != "$have" ]]; then
  echo "uv-$triple.tar.gz: sha256 $have, the release says $want" >&2
  exit 1
fi
tar -xzf "$work/uv.tar.gz" -C "$work" --strip-components 1
install -m 755 "$work/uv" "$app/Contents/MacOS/uv"

step "checks"
plutil -lint "$app/Contents/Info.plist"
printf 'LSUIElement: %s\n' "$(/usr/libexec/PlistBuddy -c 'Print :LSUIElement' "$app/Contents/Info.plist")"
"$app/Contents/MacOS/uv" --version
echo "the Python 3.15 this uv would fetch:"
# The whole list: piping it into head would let uv die of a closed pipe under pipefail.
"$app/Contents/MacOS/uv" python list --all-versions 3.15
du -sh "$app" "$app/Contents/MacOS/uv"
python3 scripts/check_bundle.py "$app"

step "the zip the CI artifact carries"
rm -f "$app.zip"
ditto -c -k --sequesterRsrc --keepParent "$app" "$app.zip"
ls -l "$app.zip"
