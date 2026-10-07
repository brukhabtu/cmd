#!/usr/bin/env bash
# Make, or bring up to date, a scratch Cargo workspace outside the repository in which
# cmd-app builds on Linux. The repository's own workspace cannot build it there: xattr
# 0.2.3, below gpui, uses libc::ENOATTR, which the libc in this tree defines for Apple and
# the BSDs and not for Linux. CI builds the app on macOS; this is for running the window on
# Linux (scripts/screenshots.sh) and for clippy on Linux (the gpui-for-cmd skill).
#
#   scripts/linux-app-workspace.sh [DIR]     DIR defaults to ${TMPDIR:-/tmp}/cmd-linux-app
#   (cd DIR && cargo build -p cmd-app)       gives DIR/target/debug/cmd
#
# Run it again after any change in the repository: it copies the current Cargo.toml,
# Cargo.lock, rust-toolchain.toml and crates/. It writes nothing in the repository and
# deletes nothing but DIR/crates, so DIR/target survives and later builds take seconds.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
dir="${1:-${TMPDIR:-/tmp}/cmd-linux-app}"

say() { printf '  %-22s %s\n' "$1" "$2"; }

# The patch below makes ENOATTR mean ENODATA on every platform xattr's Linux module covers,
# macOS among them, where that would be wrong; and macOS needs no workaround.
if [[ "$(uname)" != "Linux" ]]; then
  echo "linux-app-workspace.sh is a Linux workaround; elsewhere build cmd-app in the repository" >&2
  exit 1
fi

# Resolved before anything is made, so a refusal leaves nothing behind.
repo="$(cd "$repo" && pwd -P)"
dir="$(realpath -m "$dir")"
case "$dir/" in
  "$repo/"*)
    # Inside the repository the copies would show up as untracked files.
    echo "$dir is inside the repository; give a directory outside it" >&2
    exit 1
    ;;
esac
mkdir -p "$dir"
# DIR/crates is deleted on every run, so only a directory this script made, or an empty one,
# is written to: a mistyped path must not cost someone their own crates/.
patch_line='xattr = { path = "vendor/xattr" }'
if [[ -n "$(ls -A "$dir")" ]] && ! grep -qxF "$patch_line" "$dir/Cargo.toml" 2>/dev/null; then
  echo "$dir is not empty and holds no workspace made by this script; refusing to write there" >&2
  exit 1
fi
if grep -q '^\[patch\.crates-io\]' "$repo/Cargo.toml"; then
  # A second [patch.crates-io] table would make the copied manifest invalid TOML.
  echo "the repository's Cargo.toml has its own [patch.crates-io]; merge the xattr line into it here" >&2
  exit 1
fi

echo "scratch workspace for cmd-app on Linux: $dir"

# The repository's manifest without [profile.dev.package."*"], so dependencies build at
# cargo's plain debug settings: quicker to compile, and an app run under a virtual display
# or a clippy run has no need of optimised dependencies. Then the patch that swaps in the
# vendored xattr. The file is only rewritten when it would change, so a second run says
# so.
manifest="$(
  awk '/^\[/ { dropping = ($0 == "[profile.dev.package.\"*\"]") } !dropping' "$repo/Cargo.toml"
  printf '\n[patch.crates-io]\n%s\n' "$patch_line"
)"
if [[ -f "$dir/Cargo.toml" && "$(cat "$dir/Cargo.toml")" == "$manifest" ]]; then
  say "Cargo.toml" "unchanged"
else
  printf '%s\n' "$manifest" >"$dir/Cargo.toml"
  say "Cargo.toml" "written: the repository's, without the dev profile, with the xattr patch"
fi

# Cargo.lock keeps every other dependency at the repository's versions. Cargo rewrites the
# copy's xattr entry on each build (a path crate has no checksum), so after a build this
# reports a fresh copy every time.
for file in Cargo.lock rust-toolchain.toml; do
  if cmp -s "$repo/$file" "$dir/$file"; then
    say "$file" "unchanged"
  else
    cp "$repo/$file" "$dir/$file"
    say "$file" "copied from the repository"
  fi
done

# The xattr the lock file asks for, from cargo's registry, with ENOATTR defined as
# ENODATA: on Linux getxattr(2) names ENOATTR a synonym for ENODATA.
xattr_version="$(awk '$0 == "name = \"xattr\"" { getline; gsub(/version = |"/, ""); print; exit }' "$repo/Cargo.lock")"
if [[ -z "$xattr_version" ]]; then
  echo "Cargo.lock has no xattr; the workaround may no longer be needed" >&2
  exit 1
fi
vendored="$dir/vendor/xattr"
sys_mod="$vendored/src/sys/mod.rs"
if grep -qF '= ::libc::ENODATA;' "$sys_mod" 2>/dev/null &&
  grep -qx "version = \"$xattr_version\"" "$vendored/Cargo.toml"; then
  say "vendor/xattr" "unchanged: xattr $xattr_version, already patched"
else
  registry="${CARGO_HOME:-$HOME/.cargo}/registry/src"
  # The registry may not exist yet on a new machine; that is the fetch's case, not an error.
  in_registry() {
    find "$registry" -mindepth 2 -maxdepth 2 -type d -name "xattr-$xattr_version" -print -quit 2>/dev/null || true
  }
  source_dir="$(in_registry)"
  if [[ -z "$source_dir" ]]; then
    # --locked: the fetch only downloads into cargo's registry and never touches the lock.
    say "vendor/xattr" "xattr $xattr_version is not in $registry yet; fetching the repository's dependencies"
    (cd "$repo" && cargo fetch --locked --quiet)
    source_dir="$(in_registry)"
    if [[ -z "$source_dir" ]]; then
      echo "cargo fetch did not bring xattr $xattr_version into $registry" >&2
      exit 1
    fi
  fi
  mkdir -p "$vendored"
  cp -R "$source_dir/." "$vendored/"
  sed -i 's|= ::libc::ENOATTR;|= ::libc::ENODATA; // Linux calls a missing attribute ENODATA (scripts/linux-app-workspace.sh)|' "$sys_mod"
  # A sed that matches nothing still succeeds; the build would then fail far from here.
  if ! grep -qF '= ::libc::ENODATA;' "$sys_mod"; then
    echo "$sys_mod has no 'pub const ENOATTR ... = ::libc::ENOATTR;' to patch" >&2
    exit 1
  fi
  say "vendor/xattr" "xattr $xattr_version copied from $source_dir, ENOATTR patched to ENODATA"
fi

# Copied whole rather than synced, so a file deleted in the repository goes here too.
rm -rf "$dir/crates"
cp -R "$repo/crates" "$dir/crates"
say "crates/" "replaced with the repository's"

echo "build with: (cd $dir && cargo build -p cmd-app)"
