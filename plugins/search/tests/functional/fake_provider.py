"""A fake search provider: the tests copy it into a temporary directory and name it in a
``command`` provider, as a real tool would be named.

Its arguments are ``<mode> [items...] -- <text>``. It logs every start, with its arguments,
to ``starts.log`` beside it, then behaves as the mode says:

- ``paths``: prints each item and a newline. ``nul``: each item and a NUL byte.
- ``lines``: prints each item, a JSON object, on a line of its own. ``array``: the items
  as one JSON array.
- ``empty``: prints nothing and exits 0. ``exit1``: prints nothing and exits 1.
- ``fail``: two lines on stderr and exit 2. ``exit2-hits``: prints the items as paths,
  then a line on stderr, and exits 2, as ripgrep does for one unreadable file.
- ``slow``: sleeps far past any deadline. ``partial``: prints the items as paths, then a
  half path with no newline, then sleeps far past any deadline.
- ``noisy``: one long line on stderr with escape and control characters, and exit 2.
- ``flood``: prints the items as paths, then about 40 MB more paths, as fast as it can.
- ``garbage``: prints bytes that are neither paths nor JSON.
- ``grandchild``: prints the items as paths, starts a child that holds stdout open and
  sleeps, and exits 0 at once. ``late-grandchild``: the same after sleeping as many
  seconds as its first item says, so the call's grace for pipes ends just inside the wait.
- ``echo``: prints each item as a path, then every argument it was given as a path
  under ``/echo``, so a test sees what ``{text}`` and ``{limit}`` became.
"""

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - the fake starts a grandchild
import sys
import time
from pathlib import Path

_SLEEP = 30.0


def main() -> int:  # ruff: ignore[complex-structure, too-many-branches, too-many-return-statements] - one branch per mode
    """Do one search, as the mode says."""
    here = Path(__file__).resolve().parent
    arguments = sys.argv[1:]
    with (here / "starts.log").open("a", encoding="utf-8") as log:
        log.write(json.dumps(arguments) + "\n")
    mode = arguments[0]
    items = arguments[1 : arguments.index("--")] if "--" in arguments else arguments[1:]
    out = sys.stdout.buffer
    match mode:
        case "paths":
            out.write(b"".join(item.encode() + b"\n" for item in items))
        case "nul":
            out.write(b"".join(item.encode() + b"\0" for item in items))
        case "lines":
            out.write(b"".join(item.encode() + b"\n" for item in items))
        case "array":
            out.write(("[" + ",".join(items) + "]").encode())
        case "empty":
            return 0
        case "exit1":
            return 1
        case "fail":
            sys.stderr.write("rg: /nowhere: No such file or directory (os error 2)\nmore detail\n")
            return 2
        case "exit2-hits":
            out.write(b"".join(item.encode() + b"\n" for item in items))
            sys.stderr.write("rg: /locked: Permission denied (os error 13)\n")
            return 2
        case "slow":
            time.sleep(_SLEEP)
        case "partial":
            out.write(b"".join(item.encode() + b"\n" for item in items) + b"/half/a/pa")
            out.flush()
            time.sleep(_SLEEP)
        case "noisy":
            sys.stderr.buffer.write(b"boom \x1b[31mred\x1b[0m \x08\r" + b"y" * 500 + b"\n")
            return 2
        case "flood":
            out.write(b"".join(item.encode() + b"\n" for item in items))
            out.flush()
            line = b"/flood/" + b"x" * 90 + b"\n"
            for _ in range(400_000):  # about 40 MB, far more than the plugin keeps
                out.write(line)
        case "garbage":
            out.write(b"\xff\xfe not a path {{{ nor JSON\n\x01\x02\n")
        case "grandchild" | "late-grandchild":
            if mode == "late-grandchild":
                time.sleep(float(items.pop(0)))
            out.write(b"".join(item.encode() + b"\n" for item in items))
            out.flush()
            # The child inherits stdout and holds it open after this process exits.
            subprocess.Popen(["/bin/sleep", str(_SLEEP)])  # ruff: ignore[subprocess-without-shell-equals-true]
        case "echo":
            out.write(b"".join(item.encode() + b"\n" for item in items))
            out.write(b"".join(b"/echo/" + word.encode() + b"\n" for word in arguments))
        case _:
            sys.stderr.write(f"fake provider: no mode {mode!r}\n")
            return 64
    return 0


if __name__ == "__main__":
    sys.exit(main())
