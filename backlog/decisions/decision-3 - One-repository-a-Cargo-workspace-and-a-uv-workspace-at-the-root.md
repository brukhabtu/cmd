---
id: decision-3
title: 'One repository: a Cargo workspace and a uv workspace at the root'
date: '2026-10-07 02:41'
status: proposed
---
## Context

Rust and Python live together. The choice was one repository or two (core here, SDK and plugins elsewhere).

## Decision

One repository. The root holds a Cargo workspace (`crates/`) and a uv workspace (`python/cmd-sdk`, `plugins/*`), with shared configuration at the root and the root itself not a package.

## Consequences

- The protocol's three homes (Rust side, Python side, document) and its proof (the adapter test that runs the real plugin through uv) change in one commit, and CI sees the change whole.
- `scripts/check.sh` runs both toolchains; CI mirrors it. A contributor needs Rust and uv.
- Third-party plugins live in their own repositories and depend on `cmd-sdk` once it is published; the plugins here are the reference set.
