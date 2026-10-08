"""Plugin protocol v1, the Python side.

Newline-delimited JSON over stdin and stdout. The host sends one request per line and
the plugin answers with one response per line carrying the same ``id``. The
specification is ``docs/plugin-protocol.md`` in the cmd repository, and
``crates/cmd-core/src/protocol.rs`` is the Rust side. Change the three together.

Everything here takes data and returns data. Reading and writing lines is ``serve``'s job.
"""

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

PROTOCOL = 1
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
class PathIcon:
    """The icon the system shows for whatever sits at an absolute path.

    An application bundle gives its own icon, a document its type's, a folder a folder.
    A path that does not exist leaves the row without an icon; it is never an error.
    """

    path: str


@dataclass(frozen=True)
class SymbolIcon:
    """A system symbol by name, drawn in the row's text colour.

    A name the system does not know leaves the row without an icon; it is never an error.
    """

    name: str


type Icon = PathIcon | SymbolIcon
"""What a row shows beside its text. The window resolves it; a plugin only names it."""


@dataclass(frozen=True)
class Item:
    """One row in the result list.

    ``score`` is a confidence in ``0.0..=1.0`` for fuzzy matches. Leave it ``None`` for a
    definite answer, which the host ranks above every fuzzy one. The first action is the
    one Enter runs; with no actions the host sends ``DEFAULT_ACTION``. ``icon`` is the
    one field version 1 added, so it comes last: a plugin written against version 0
    constructs an item positionally and still does.
    """

    id: str
    title: str
    subtitle: str | None = None
    score: float | None = None
    actions: tuple[Action, ...] = ()
    icon: Icon | None = None


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
    """A line from the host that is not a request this SDK understands.

    ``request_id`` is the line's own id when it had a readable one, and 0 when it had none,
    so the answer can name the request it belongs to.
    """

    def __init__(self, message: str, request_id: int = 0) -> None:
        super().__init__(message)
        self.request_id = request_id


class UnknownMethodError(MalformedRequestError):
    """A request for a method this SDK does not have, a newer protocol's perhaps."""


class InvalidAnswerError(ValueError):
    """A plugin returned something the protocol cannot carry.

    The message names the item or the field, so the plugin's author can find it.
    """


_METHODS = ("describe", "query", "run")


def decode_request(line: str) -> Request:
    """Parse one line from the host.

    Raises:
        UnknownMethodError: The line is a request, but for a method this SDK does not have.
        MalformedRequestError: The line is not JSON, or not a request of a known method.
    """
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as error:
        raise MalformedRequestError(f"not JSON: {error.msg}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), int):
        raise MalformedRequestError("a request is an object with an integer id")
    request_id = raw["id"]
    # The method is read before the params, so a request for a method this SDK lacks is
    # answered as that, with its id, whatever its params look like.
    method = raw.get("method")
    if not isinstance(method, str):
        raise MalformedRequestError("a request has a method, a string", request_id)
    if method not in _METHODS:
        raise UnknownMethodError(f"unknown method {method!r}", request_id)
    params = raw.get("params")
    if not isinstance(params, dict):
        raise MalformedRequestError("params must be an object", request_id)
    try:
        return _decode_params(method, request_id, params)
    except MalformedRequestError as error:
        error.request_id = request_id
        raise


def _decode_params(method: str, request_id: int, params: Mapping[str, Any]) -> Request:
    match method:
        case "describe":
            return Describe(request_id, _field(params, "protocol", int))
        case "query":
            return Query(request_id, _field(params, "text", str))
        case "run":
            return Run(request_id, _field(params, "item", str), _field(params, "action", str))
        case _:
            # _METHODS and this match name the same methods; if they drift, say so here.
            raise UnknownMethodError(f"unknown method {method!r}", request_id)


def dispatch(request: Request, plugin: Plugin) -> Success:
    """Answer one request with the plugin's functions.

    Whatever the plugin's own functions raise passes through, and so does
    ``InvalidAnswerError`` for an answer the protocol cannot carry; ``serve`` turns either
    into an error response at the boundary.
    """
    match request:
        case Describe():
            return Success(request.id, _description_json(plugin.description))
        case Query():
            items = plugin.query(request.text)
            body = [_item_json(item, position) for position, item in enumerate(items, 1)]
            return Success(request.id, {"items": body})
        case Run():
            effect = plugin.run(request.item, request.action)
            return Success(request.id, {"effect": _effect_json(effect)})
        case _ as unreachable:
            assert_never(unreachable)


def encode_response(response: Response) -> str:
    """Serialise a response as one line, newline included.

    A ``ValueError`` means the response holds something that cannot go on the wire: a NaN
    or an infinity, which JSON has no form for, or text that is not valid Unicode, such as
    a file name Python read from bytes that were not UTF-8. ``serve`` answers with a
    ``plugin_error`` instead.
    """
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
    line = json.dumps(body, ensure_ascii=False, allow_nan=False) + "\n"
    # dumps keeps a lone surrogate as it is, and the write to the stream would be the
    # first to find it. Encoding here finds it where serve can still answer.
    line.encode("utf-8")
    return line


# --- JSON shapes ----------------------------------------------------------------------


def _field[T](params: Mapping[str, Any], name: str, kind: type[T]) -> T:
    value = params.get(name)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise MalformedRequestError(f"params.{name} must be a {kind.__name__}")
    return value


def _text(value: object, what: str) -> str:
    """The value if it is text.

    Raises:
        InvalidAnswerError: It is not, and the message names ``what``.
    """
    if not isinstance(value, str):
        raise InvalidAnswerError(f"{what} must be a str, not {type(value).__name__}")
    return value


def _score(value: object) -> float:
    """The value if it is a finite number, which is all JSON can carry as one.

    Raises:
        InvalidAnswerError: It is a bool, not a number, or a NaN or an infinity.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidAnswerError(f"score must be a number, not {type(value).__name__}")
    try:
        finite = math.isfinite(value)
    except OverflowError:  # an int too large for a float
        finite = False
    if not finite:
        shown = value if isinstance(value, float) else "too large to be a float"
        raise InvalidAnswerError(f"score is {shown}, and must be a finite number")
    return value


def _description_json(description: Description) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": _text(description.name, "description name"),
        "version": _text(description.version, "description version"),
        "protocol": PROTOCOL,
    }
    if description.keyword is not None:
        body["keyword"] = _text(description.keyword, "description keyword")
    return body


def _item_json(item: object, position: int) -> dict[str, Any]:
    """One item as JSON, with its fields checked.

    Raises:
        InvalidAnswerError: It is not an ``Item`` or a field is wrong. The message names the
            item by its place in the answer and its id, so the author can find it.
    """
    if not isinstance(item, Item):
        raise InvalidAnswerError(
            f"query must return Items, and item {position} is a {type(item).__name__}"
        )
    label = f"item {position}" + (f" ({item.id!r})" if isinstance(item.id, str) else "")
    try:
        return _checked_item_json(item)
    except InvalidAnswerError as problem:
        raise InvalidAnswerError(f"{label}: {problem}") from None


def _checked_item_json(item: Item) -> dict[str, Any]:
    body: dict[str, Any] = {"id": _text(item.id, "id"), "title": _text(item.title, "title")}
    if item.subtitle is not None:
        body["subtitle"] = _text(item.subtitle, "subtitle")
    if item.score is not None:
        body["score"] = _score(item.score)
    if item.actions:
        if not isinstance(item.actions, tuple | list):
            raise InvalidAnswerError(
                f"actions must be a tuple or list of Actions, not {type(item.actions).__name__}"
            )
        body["actions"] = [_action_json(action) for action in item.actions]
    if item.icon is not None:
        body["icon"] = _icon_json(item.icon)
    return body


def _action_json(action: object) -> dict[str, str]:
    if not isinstance(action, Action):
        raise InvalidAnswerError(f"an action must be an Action, not {type(action).__name__}")
    return {"id": _text(action.id, "action id"), "title": _text(action.title, "action title")}


def _icon_json(icon: Icon) -> dict[str, str]:
    if not isinstance(icon, PathIcon | SymbolIcon):
        raise InvalidAnswerError(
            f"icon must be a PathIcon or a SymbolIcon, not {type(icon).__name__}"
        )
    match icon:
        case PathIcon():
            return {"kind": "path", "path": _text(icon.path, "icon path")}
        case SymbolIcon():
            return {"kind": "symbol", "name": _text(icon.name, "icon name")}
        case _ as unreachable:
            assert_never(unreachable)


def _effect_json(effect: Effect) -> dict[str, str]:
    if not isinstance(effect, Close | Copy | Open | Show):
        raise InvalidAnswerError(
            f"run must return a Close, Copy, Open or Show, not {type(effect).__name__}"
        )
    match effect:
        case Close():
            return {"kind": "close"}
        case Copy():
            return {"kind": "copy", "text": _text(effect.text, "copy text")}
        case Open():
            return {"kind": "open", "target": _text(effect.target, "open target")}
        case Show():
            return {"kind": "show", "text": _text(effect.text, "show text")}
        case _ as unreachable:
            assert_never(unreachable)
