---
paths:
  - "**/*.rs"
---
# Editing Rust that cargo fmt has formatted

`cargo fmt --all` runs before every check and commit here, and it rewraps anything over
the line width. An edit that looks for the exact text that was written a moment ago
misses once formatting has moved it, and the miss is silent: the script reports success
or asserts late, and the build then fails on the half that did not land.

- Replace a whole item (a function, a test, an enum variant and its doc comment) between
  two stable one-line anchors, or rewrite the file. Never match a multi-line expression
  that formatting may have rewrapped.
- Verify every replacement landed (`assert` or a `grep -n` of a token the edit introduced)
  before running the build, and stop the chain on the first miss.
- A command that edits, builds and commits in one line stops on the build's own exit
  status, never on the exit status of a subshell or a `grep` that read it.

Why this rule exists: in the milestone 1 session, five edit scripts in a row silently
missed formatted text, one push went out with a compile error because a subshell's exit
code hid the failed build, and each miss cost a build cycle to notice.
