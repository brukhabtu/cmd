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
    agreement = BEFORE_DESCRIBE
    for line in source:
        if not line.strip():
            continue
        answer, agreement = _answer(line, plugin, agreement)
        sink.write(answer)
        sink.flush()


def _answer(line: str, plugin: Plugin, agreement: Agreement) -> tuple[str, Agreement]:
    """The line to write for one request line, and the agreement from then on.

    It is always an answer and never raises.
    """
    try:
        request = decode_request(line)
    except UnknownMethodError as error:
        return encode_response(Failure(error.request_id, "unknown_method", str(error))), agreement
    except MalformedRequestError as error:
        return encode_response(Failure(error.request_id, "bad_request", str(error))), agreement
    if isinstance(request, Describe):
        agreement = agree(request)
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
