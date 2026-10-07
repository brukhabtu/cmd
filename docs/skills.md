# Skills: proposed at milestones, built on evidence, accepted by eval

Claude Code skills for this repository live in the `cmd-dev` plugin at
`.claude/plugins/cmd-dev`. The plugin is enabled for every session by `.claude/settings.json`.

## When a skill is proposed

At two moments in every milestone, the person driving the work writes a short skill review:

- **Before the milestone starts:** what the coming work will make the model do repeatedly,
  where it has been wrong before, and which facts it keeps re-deriving.
- **After the milestone closes:** what the model demonstrably got wrong during the work, and
  what it kept looking up. Evidence is a transcript, a reverted commit, or a failed check.

Each candidate becomes a draft on the board, titled `Skill: <name>`, with the evidence and
the eval cases it would have to pass written into the description. A candidate without
evidence stays a draft. This follows the standing rule: a skill is added after the model has
got something wrong, never in anticipation.

## What a skill ships with

```
.claude/plugins/cmd-dev/
  skills/<name>/SKILL.md
  evals/<name>-<case>/prompt.md       the prompt as it was really asked
  evals/<name>-<case>/graders/*.md    one grader per file
```

At least three cases, each from a real miss. Graders are deterministic where they can be
(`regex`, `tool_used`, `tool_order`, `file_exists`) and `llm` only where the judgment needs
a rubric. The test is the one from the standing constraints: if you could write an
assertion for it, write it as a deterministic grader; if you would need a rubric, write an
`llm` grader.

## The gate

A skill is accepted, and its draft promoted, when all four hold:

1. `claude plugin validate --strict .claude/plugins/cmd-dev` passes.
2. `claude plugin eval .claude/plugins/cmd-dev --threshold 1.0 --ablation with-without`
   passes at the default three runs per case. Locally, narrow it with `--case '<name>-*'`.
3. Every case scores higher with the plugin than without it: `scripts/eval_gate.py` reads
   the `--json` result and fails on a delta of zero or less. A skill that changes nothing
   is not a skill.
4. The eval result (the `eval-result` artifact from CI, or the local `--json` file) is
   attached to the draft before promotion.

CI (`.github/workflows/skills.yml`) runs steps 1 to 3 over the whole suite whenever a
change touches `.claude/plugins/cmd-dev/`, and uploads the result. With no cases in the
plugin there is nothing to gate and the job passes. Each case is a real agent session on
the credential the GitHub App setup stored as a repository secret, `CLAUDE_CODE_OAUTH_TOKEN`
for a subscription or `ANTHROPIC_API_KEY` for a Console key, so the job carries a cost
ceiling. No further secret is needed.

## Retiring a skill

A skill whose cases pass without it for two milestones in a row is removed, cases and all.
Principles last and techniques expire.

## Candidates

Candidates live on the board, not here. `backlog draft list --plain` shows them.
