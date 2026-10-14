"""The shell: read requests from one stream, write responses to another."""

import contextlib
import sys
from typing import TextIO

from cmd_sdk.protocol import (
    BEFORE_DESCRIBE,
    Agreement,
    Describe,
    Failure,
    MalformedRequestError,
    Plugin,
    UnknownMethodError,
    agree,
    decode_request,
    dispatch,
    encode_response,
)
from cmd_sdk.reporter import Reporter, installed


def serve(plugin: Plugin, source: TextIO | None = None, sink: TextIO | None = None) -> None:
    """Answer requests until the source closes.

    ``source`` defaults to stdin and ``sink`` to stdout. Pass streams of your own in a
    test.

    Every request line gets exactly one answer, and the loop goes on after each:

    - A line the SDK cannot read gets a ``bad_request`` error, and a request for a method
      it does not have an ``unknown_method`` error. Both carry the request's own id when
      the line had one.
    - An exception from the plugin's own functions, or an answer the protocol cannot carry
      (an icon path that is not text, a score that is NaN, an effect kind the agreed
      version lacks), gets a ``plugin_error`` that says what it was.

    ``describe`` sets the version and the capabilities every later answer holds to: the
    lower of the host's version and the SDK's, and the names the host sent.

    ``serve`` owns the stream: answers are written under the lock that ``report`` takes for a
    task, so a plugin's background threads can call ``cmd_sdk.report`` while a request is
    answered and no two lines interleave.

    While serving to stdout, ``print`` writes to stderr instead: stdout belongs to the
    protocol, and a line on it the host cannot read costs the answer it landed in.
    """
    source = sys.stdin if source is None else source
    sink = sys.stdout if sink is None else sink
    if sink is sys.stdout:
        with contextlib.redirect_stdout(sys.stderr):
            _loop(plugin, source, sink)
    else:
        _loop(plugin, source, sink)


def _loop(plugin: Plugin, source: TextIO, sink: TextIO) -> None:
    reporter = Reporter(sink)
    agreement = BEFORE_DESCRIBE
    with installed(reporter):
        for line in source:
            if not line.strip():
                continue
            answer, agreement = _answer(line, plugin, agreement, reporter)
            reporter.write(answer)


def _answer(
    line: str, plugin: Plugin, agreement: Agreement, reporter: Reporter
) -> tuple[str, Agreement]:
    """The line to write for one request line, and the agreement from then on.

    It is always an answer and never raises. The reporter learns the agreement before the
    plugin's ``describe`` runs, so a thread that function starts can report at once.
    """
    try:
        request = decode_request(line)
    except UnknownMethodError as error:
        return encode_response(Failure(error.request_id, "unknown_method", str(error))), agreement
    except MalformedRequestError as error:
        return encode_response(Failure(error.request_id, "bad_request", str(error))), agreement
    if isinstance(request, Describe):
        agreement = agree(request)
        reporter.agree(agreement)
    try:
        # Encoding is inside the guard: a value JSON cannot carry fails here, as an answer,
        # and not on the write, as the end of the session.
        return encode_response(dispatch(request, plugin, agreement)), agreement
    except (Exception, SystemExit) as error:  # ruff: ignore[blind-except] - a plugin's failure, even its sys.exit(), must not end the session
        failure = Failure(request.id, "plugin_error", _failure_message(error))
        return encode_response(failure), agreement


def _failure_message(error: BaseException) -> str:
    """What the error says, in text that always encodes: an odd character is escaped."""
    message = f"{type(error).__name__}: {error}"
    return message.encode("utf-8", "backslashreplace").decode("utf-8")
