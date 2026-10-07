"""The world is a child process; here the children are harmless Python one-liners."""

import sys
import time

from system import execute


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_a_command_that_exits_zero_is_a_success() -> None:
    assert execute(_python("pass")) is None


def test_the_last_line_of_stderr_names_the_failure() -> None:
    code = "import sys; print('noise', file=sys.stderr); print('bad thing', file=sys.stderr); sys.exit(3)"
    assert execute(_python(code)) == "bad thing"


def test_a_silent_failure_names_the_exit_status() -> None:
    failure = execute(_python("raise SystemExit(4)"))
    assert failure is not None
    assert "exited with 4" in failure


def test_a_missing_binary_is_reported_not_raised() -> None:
    failure = execute(["/nonexistent/system-plugin-test/binary"])
    assert failure is not None
    assert "No such file or directory" in failure


def test_a_slow_command_is_left_to_finish_and_counts_as_success() -> None:
    started = time.monotonic()
    assert execute(_python("import time; time.sleep(1)"), patience=0.2) is None
    assert time.monotonic() - started < 0.8
