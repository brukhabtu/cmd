"""The world is a child process; here the children are harmless Python one-liners."""

import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import time
from pathlib import Path

import pytest
from cmd_sdk import call


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_a_finished_child_gives_its_code_and_both_streams() -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    result = call(_python(code), 10)
    assert (result.returncode, result.stdout, result.stderr) == (3, b"out\n", b"err\n")
    assert not result.timed_out


def test_a_slow_child_times_out_and_keeps_partial_output() -> None:
    code = "import time; print('early', flush=True); time.sleep(5)"
    start = time.monotonic()
    result = call(_python(code), 0.5)
    assert time.monotonic() - start < 3
    assert result.timed_out
    assert result.returncode is None
    assert result.stdout == b"early\n"


def test_a_slow_child_is_left_to_finish(tmp_path: Path) -> None:
    marker = tmp_path / "done"
    code = f"import time, pathlib; time.sleep(0.5); pathlib.Path({str(marker)!r}).write_text('x')"
    assert call(_python(code), 0.1).timed_out
    assert not marker.exists()
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.exists()


def test_a_large_output_does_not_block_the_child() -> None:
    result = call(_python("import sys; sys.stdout.write('x' * 1_000_000)"), 10)
    assert result.returncode == 0
    assert len(result.stdout) == 1_000_000


def test_a_child_cannot_write_to_the_callers_stdout() -> None:
    # Run the call in a process whose real stdout we read: nothing of the child's may reach it.
    script = (
        "import sys; from cmd_sdk import call; "
        "r = call([sys.executable, '-c', 'print(\"leak\")'], 10); "
        "print('captured', r.stdout.decode().strip())"
    )
    done = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ},
    )
    assert done.stdout == "captured leak\n"


def test_a_child_cannot_read_the_callers_stdin() -> None:
    result = call(_python("import sys; print(repr(sys.stdin.read()))"), 10)
    assert result.stdout == b"''\n"


def test_a_missing_program_raises_os_error() -> None:
    with pytest.raises(FileNotFoundError):
        call(["/nonexistent/cmd-sdk-test/binary"], 1)


def test_a_string_is_not_a_command() -> None:
    with pytest.raises(TypeError, match="list"):
        call("echo hi", 1)


def test_a_slow_child_is_killed_when_asked(tmp_path: Path) -> None:
    marker = tmp_path / "done"
    code = f"import time, pathlib; time.sleep(1); pathlib.Path({str(marker)!r}).write_text('x')"
    result = call(_python(code), 0.1, kill_on_timeout=True)
    assert result.timed_out
    time.sleep(1.5)
    assert not marker.exists()


def test_stdout_can_be_discarded_while_stderr_is_kept() -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr)"
    result = call(_python(code), 10, keep_stdout=False)
    assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"err\n")


def test_a_grandchild_holding_the_pipes_costs_one_grace_not_two() -> None:
    code = "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3)']); print('hi')"
    start = time.monotonic()
    result = call(_python(code), 10)
    assert result.stdout == b"hi\n"
    assert time.monotonic() - start < 1.8
