# The retry handler as a generator of effects

The "Core and shell" section of `idioms.md` writes a retry handler as a function that returns the next step. This is the same handler written as a generator, to show what the second entry in that section looks like and what it costs. The logic yields a description of each effect and gets the result back through `send()`, so it reads top to bottom and never touches the network itself.

## The logic

```python
@dataclass(frozen=True)
class Send:
    request: Request


@dataclass(frozen=True)
class RefreshToken: ...


@dataclass(frozen=True)
class Sleep:
    seconds: float


type Effect = Send | RefreshToken | Sleep
type Steps = Generator[Effect, Response | None, Response]


def send_with_retry(request: Request) -> Steps:
    """Yield the effects for sending a request with an auth refresh and retries.

    Raises:
        HttpError: The last response was not a success.
    """
    attempt = 1
    while True:
        response = yield Send(request)
        assert isinstance(response, Response)
        if 200 <= response.status < 300:
            return response
        if response.status == 401 and attempt == 1:
            yield RefreshToken()
        elif response.status >= 500 and attempt < 3:
            yield Sleep(0.2 * 2.0**attempt)
        else:
            raise HttpError(response.status)
        attempt += 1
```

## The shell

The shell is a generic runner. It performs each effect and feeds the answer back in.

```python
def run(steps: Steps) -> Response:
    reply: Response | None = None
    while True:
        try:
            effect = steps.send(reply)
        except StopIteration as done:
            result: Response = done.value
            return result
        match effect:
            case Send(request=request):
                reply = send(request)
            case RefreshToken():
                refresh_token()
                reply = None
            case Sleep(seconds=seconds):
                time.sleep(seconds)
                reply = None
            case _ as unreachable:
                assert_never(unreachable)
```

## The test

A test drives the generator by hand and needs no fakes.

```python
steps = send_with_retry(request)
assert next(steps) == Send(request)
assert steps.send(Response(503)) == Sleep(0.4)
assert steps.send(None) == Send(request)
with pytest.raises(StopIteration) as done:
    steps.send(Response(200))
assert done.value.value == Response(200)
```

## What it costs

- **Reply types are loose.** Every `yield` receives the same reply type, so the type checker cannot know that a `Send` is answered with a `Response`. The `assert isinstance` line is there for that reason.
- **The return value arrives in an exception.** `StopIteration` carries the result, which cuts against the rule that exceptions are never control flow.
- **Tests are coupled to the order of effects.** The test above spells out the whole conversation, so reordering two yields breaks it even when the behaviour is unchanged.
- **Composition needs `yield from`.** Any helper that performs an effect has to be a generator too, and that spreads through the call chain the way `async` does.

## Which one to use

Returning a step is plainer and its tests are one line each, so the retry handler stays in that form. The generator earns its place when the logic and the I/O alternate many times, because the returned step would then need a state machine in the shell.
