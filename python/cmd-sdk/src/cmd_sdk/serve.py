"""The shell: read requests from one stream, write responses to another."""

import sys
from typing import TextIO

from cmd_sdk.protocol import (
    Err,
    MalformedRequestError,
    Plugin,
    Response,
    decode_request,
    dispatch,
    encode_response,
)


def serve(plugin: Plugin, source: TextIO | None = None, sink: TextIO | None = None) -> None:
    """Answer requests until the source closes.

    ``source`` defaults to stdin and ``sink`` to stdout. Pass streams of your own in a
    test. A request the SDK cannot read gets a ``bad_request`` error; an exception from
    the plugin's own functions gets a ``plugin_error`` and the loop goes on.
    """
    source = sys.stdin if source is None else source
    sink = sys.stdout if sink is None else sink
    for line in source:
        if not line.strip():
            continue
        sink.write(encode_response(_answer(line, plugin)))
        sink.flush()


def _answer(line: str, plugin: Plugin) -> Response:
    try:
        request = decode_request(line)
    except MalformedRequestError as error:
        return Err(0, "bad_request", str(error))
    try:
        return dispatch(request, plugin)
    except Exception as error:  # ruff: ignore[blind-except] - the plugin's failure must not end the session
        return Err(request.id, "plugin_error", f"{type(error).__name__}: {error}")
