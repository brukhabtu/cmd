---
id: decision-2
title: Python 3.15 is the floor for the SDK and the plugins
date: '2026-10-07 02:41'
status: proposed
---
## Context

The repository owner's standard sets Python 3.15 as the floor for owned projects, before it is final. The SDK is also the surface other people write against, and a high floor costs adopters.

## Decision

`requires-python = ">=3.15"` for the SDK and every plugin in this repository. uv installs the pre-release on demand, so the floor costs a contributor nothing but a download.

## Consequences

- The idioms the SDK is written in (`type` aliases, PEP 695 generics, deferred annotations) are available everywhere in the code.
- A plugin author on an older Python cannot use the SDK until they upgrade, which uv makes a one-line step. If adoption shows this is a real barrier, lowering the SDK's floor to 3.13 is a one-line change and the idioms that need 3.14 or 3.15 move behind version checks. Revisit at milestone 4.
- mypy is pinned to a version that understands 3.15; ruff targets py314 until it knows py315.
