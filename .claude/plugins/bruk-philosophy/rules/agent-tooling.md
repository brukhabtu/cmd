---
paths:
  - "**/SKILL.md"
  - "**/CLAUDE.md"
  - "**/CLAUDE.local.md"
  - "**/.claude/rules/**"
  - "**/.claude/skills/**"
  - "**/.claude/agents/**"
  - "**/.claude/commands/**"
  - "**/.claude/settings*.json"
  - "**/.claude-plugin/**"
  - "**/hooks/hooks.json"
---
# Agent tooling

Applies when authoring or reviewing Claude Code extensions: CLAUDE.md, rules, skills,
agents, hooks, and plugins.

When a line here makes the extension harder to read, harder to change, or harder to
ship, drop it.

## Deterministic where it can be

- The deterministic execution matrix has two axes: whether execution is deterministic
  or probabilistic, and whether output is. A mechanical check is invoked
  deterministically, by a script, a hook, CI, or a fixed SDK call. It is never left to
  an agent's or a skill's discretion.
- A skill may invoke those tools and reason about the results. It is never the sole
  trigger for a check that needs high reliability.
- Judgment may set a check's scope or target, as long as the check is guaranteed to
  fire.
- A block that needs no judgment is a hook, and its message gives the equivalent
  command. No enforcement without the reason attached.

## Which primitive carries what

- Mechanise the scaffolding with hooks, lint rules, and tools. Leave the core act to
  prose in skills and agents. Let each piece load only when it is needed.
- CLAUDE.md is brief and authoritative, and everything else points at it. Capture the
  philosophy once and do not repeat constraints.
- A workflow document states principles and leaves the judgment to the agent. It is not
  a checklist.
- A property such as "cannot edit" is set by an agent's tool policy. Prose in its prompt
  does not enforce it.
- Favour CodeAct and CLI-first patterns over MCP for most tool surfaces.
- Context engineering is a first-class discipline.

## When to add one

- Add a skill or a rule after the model has demonstrably got something wrong. Never add
  one in anticipation.
- Get evals working for one specific skill before building an eval library, and extract
  the library only once that one case is proven.
- Adjust model and effort choices from evals, not from taste.
