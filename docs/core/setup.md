# Setting up

You need the Rust toolchain that `rust-toolchain.toml` pins (rustup reads it), and
[uv](https://docs.astral.sh/uv/), which brings Python 3.15 and every Python tool the
checks use.

```sh
uv sync --all-packages --all-groups   # Python 3.15, the SDK, the plugins, the tools
scripts/check.sh                       # what CI runs, in the same order
scripts/docs.sh                        # this site, into site/
```

## On a Mac

Everything builds, including the app: `cargo run -p cmd-app`.

GPUI compiles its shaders with Apple's Metal compiler while it builds, so the Mac needs
full Xcode, not only the Command Line Tools. If the build stops with `gpui ... metal
shader compilation failed`, the compiler is missing or not the one in use:

```sh
xcode-select -p                              # should end in Xcode.app/Contents/Developer
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -license accept              # a fresh Xcode refuses to run until this is done
xcrun -f metal                               # prints a path when the compiler is found
xcodebuild -downloadComponent MetalToolchain # Xcode 26 and later ship the compiler as a download
```

Open Xcode once after a download, then build again. The CI job on `macos-latest` has all
of this, which is why it builds there.

## On Linux

Everything but the app builds and is tested: a clash between `xattr` and `libc` far below
GPUI stops `crates/cmd-app` compiling there, so the checks use
`cargo test --workspace --exclude cmd-app`, and CI builds the app on macOS. To compile and
lint the app on Linux, `scripts/linux-app-workspace.sh` makes a scratch workspace outside
the repository with that clash patched.

!!! abstract "To be written"
    Editors, debugging the window, running one plugin against the host, and the CI jobs.
    Tracked by the documentation epic (TASK-1.43).
