"""Plugin protocol v0, the Python side.

Newline-delimited JSON over stdin and stdout. The host sends one request per line and
the plugin answers with one response per line carrying the same ``id``. The
specification is ``docs/plugin-protocol.md`` in the cmd repository, and
``crates/cmd-core/src/protocol.rs`` is the Rust side. Change the three together.

Everything here takes data and returns data. Reading and writing lines is ``serve``'s job.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

PROTOCOL = 0
"""The protocol version this SDK speaks."""

DEFAULT_ACTION = "default"
"""The action id the host sends when an item declared no actions."""


# --- what a plugin produces -----------------------------------------------------------


@dataclass(frozen=True)
class Description:
    """What a plugin says about itself in the handshake.

    With a keyword, the plugin sees only queries whose first word is the keyword, and the
    keyword is stripped before ``query`` is called. Without one, it sees every query.
    """

    name: str
    version: str
    keyword: str | None = None


@dataclass(frozen=True)
class Action:
    """Something that can be done with an item."""

    id: str
    title: str


@dataclass(frozen=True)
class Item:
    """One row in the result list.

    ``score`` is a confidence in ``0.0..=1.0`` for fuzzy matches. Leave it ``None`` for a
    definite answer, which the host ranks above every fuzzy one. The first action is the
    one Enter runs; with no actions the host sends ``DEFAULT_ACTION``.
    """

    id: str
    title: str
    subtitle: str | None = None
    score: float | None = None
    actions: tuple[Action, ...] = ()


@dataclass(frozen=True)
class Close:
    """Hide the launcher."""


@dataclass(frozen=True)
class Copy:
    """Put text on the clipboard, then hide."""

    text: str


@dataclass(frozen=True)
class Open:
    """Open a URL or a path with the system handler, then hide."""

    target: str


@dataclass(frozen=True)
class Show:
    """Keep the launcher open and show a message."""

    text: str


type Effect = Close | Copy | Open | Show
"""What the host does after an action ran. The plugin returns it; the host performs it."""


@dataclass(frozen=True)
class Plugin:
    """A cmd plugin: a description and two functions.

    ``query`` receives the typed text with the plugin's keyword already stripped and
    returns the items to show. ``run`` receives the id of the chosen item and the id of
    the chosen action (``DEFAULT_ACTION`` when the item declared none) and returns the
    effect the host should perform.
    """

    description: Description
    query: Callable[[str], Sequence[Item]]
    run: Callable[[str, str], Effect]


# --- the wire -------------------------------------------------------------------------


@dataclass(frozen=True)
class Describe:
    """The handshake. ``protocol`` is the version the host speaks."""

    id: int
    protocol: int


@dataclass(frozen=True)
class Query:
    """The typed text, already stripped of the plugin's keyword."""

    id: int
    text: str


@dataclass(frozen=True)
class Run:
    """The person chose an item and an action."""

    id: int
    item: str
    action: str


type Request = Describe | Query | Run


@dataclass(frozen=True)
class Success:
    """A result for the request with this id."""

    id: int
    result: Mapping[str, Any]


@dataclass(frozen=True)
class Failure:
    """A failure instead of a result."""

    id: int
    code: str
    message: str


type Response = Success | Failure


class MalformedRequestError(ValueError):
    """A line from the host that is not a request this SDK understands."""


def decode_request(line: str) -> Request:
    """Parse one line from the host.

    Raises:
        MalformedRequestError: The line is not JSON, or not a request of a known method.
    """
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as error:
        raise MalformedRequestError(f"not JSON: {error.msg}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), int):
        raise MalformedRequestError("a request is an object with an integer id")
    request_id = raw["id"]
    params = raw.get("params")
    if not isinstance(params, dict):
        raise MalformedRequestError("params must be an object")
    match raw.get("method"):
        case "describe":
            return Describe(request_id, _field(params, "protocol", int))
        case "query":
            return Query(request_id, _field(params, "text", str))
        case "run":
            return Run(request_id, _field(params, "item", str), _field(params, "action", str))
        case other:
            raise MalformedRequestError(f"unknown method {other!r}")


def dispatch(request: Request, plugin: Plugin) -> Success:
    """Answer one request with the plugin's functions.

    Whatever the plugin's own functions raise passes through; ``serve`` turns it into an
    error response at the boundary.
    """
    match request:
        case Describe():
            return Success(request.id, _description_json(plugin.description))
        case Query():
            items = plugin.query(request.text)
            return Success(request.id, {"items": [_item_json(item) for item in items]})
        case Run():
            effect = plugin.run(request.item, request.action)
            return Success(request.id, {"effect": _effect_json(effect)})
        case _ as unreachable:
            assert_never(unreachable)


def encode_response(response: Response) -> str:
    """Serialise a response as one line, newline included."""
    match response:
        case Success():
            body: dict[str, Any] = {"id": response.id, "result": response.result}
        case Failure():
            body = {
                "id": response.id,
                "error": {"code": response.code, "message": response.message},
            }
        case _ as unreachable:
            assert_never(unreachable)
    return json.dumps(body, ensure_ascii=False) + "\n"


# --- JSON shapes ----------------------------------------------------------------------


def _field[T](params: Mapping[str, Any], name: str, kind: type[T]) -> T:
    value = params.get(name)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise MalformedRequestError(f"params.{name} must be a {kind.__name__}")
    return value


def _description_json(description: Description) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": description.name,
        "version": description.version,
        "protocol": PROTOCOL,
    }
    if description.keyword is not None:
        body["keyword"] = description.keyword
    return body


def _item_json(item: Item) -> dict[str, Any]:
    body: dict[str, Any] = {"id": item.id, "title": item.title}
    if item.subtitle is not None:
        body["subtitle"] = item.subtitle
    if item.score is not None:
        body["score"] = item.score
    if item.actions:
        body["actions"] = [{"id": action.id, "title": action.title} for action in item.actions]
    return body


def _effect_json(effect: Effect) -> dict[str, str]:
    match effect:
        case Close():
            return {"kind": "close"}
        case Copy():
            return {"kind": "copy", "text": effect.text}
        case Open():
            return {"kind": "open", "target": effect.target}
        case Show():
            return {"kind": "show", "text": effect.text}
        case _ as unreachable:
            assert_never(unreachable)
