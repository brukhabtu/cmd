---
paths:
  - "**/tests/**/*.py"
  - "**/test/**/*.py"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/conftest.py"
mode: owner
---
# Python tests

Applies when reading or writing Python tests in a repository I own.

When a line here makes the tests harder to read, harder to change, or harder to ship,
drop it.

## Four layers, named for what they prove

- `tests/unit/` proves logic. The functions are pure and the tests use no doubles.
- `tests/functional/` proves behaviour, with the world faked at the boundary. It is the
  only layer that uses doubles.
- `tests/adapter/` proves one gateway against the real thing.
- `tests/e2e/` is the end-to-end layer.
- "Integration test" is a retired term.

## Doubles

- Doubles appear only at the world boundary, and only as fakes. The test asserts on the
  fake's state.
- How hard a test is to write says something about the code. When a test needs a page
  of setup and a stack of mocks, the code made that choice at writing time.

## Order and running

- Work outside-in.
- Test shells lightly.
- The functional suite runs twice in one process, to catch state leakage.
