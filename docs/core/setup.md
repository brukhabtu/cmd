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

## On Linux

Everything but the app builds and is tested: a clash between `xattr` and `libc` far below
GPUI stops `crates/cmd-app` compiling there, so the checks use
`cargo test --workspace --exclude cmd-app`, and CI builds the app on macOS. To compile and
lint the app on Linux, `scripts/linux-app-workspace.sh` makes a scratch workspace outside
the repository with that clash patched.

!!! abstract "To be written"
    Editors, debugging the window, running one plugin against the host, and the CI jobs.
    Tracked by the documentation epic (TASK-1.43).
