"""A fake qmd that answers with a capture of the real one.

The tests copy it into a temporary directory and name it as a qmd provider's ``bin``. What
it answers comes through the provider's ``env`` table, so the ``/usr/bin/env`` prefix is
exercised too: ``FAKE_QMD_OUT`` names a file printed on stdout, ``FAKE_QMD_ERR`` one printed
on stderr, and ``FAKE_QMD_EXIT`` is the exit code. Every call's arguments and that
environment are logged to ``calls.log`` beside it.
"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """Answer one call with the captured output."""
    here = Path(__file__).resolve().parent
    seen = {key: value for key, value in os.environ.items() if key.startswith("FAKE_QMD_")}
    seen["PATH"] = os.environ.get("PATH", "")
    with (here / "calls.log").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"argv": sys.argv[1:], "env": seen, "cwd": str(Path.cwd())}) + "\n")
    if out := os.environ.get("FAKE_QMD_OUT"):
        sys.stdout.buffer.write(Path(out).read_bytes())
    if err := os.environ.get("FAKE_QMD_ERR"):
        sys.stderr.buffer.write(Path(err).read_bytes())
    return int(os.environ.get("FAKE_QMD_EXIT", "0"))


if __name__ == "__main__":
    sys.exit(main())
