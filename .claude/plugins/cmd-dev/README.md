# cmd-dev

The Claude Code skills for working on this repository, and their evals.

There are no skills yet, on purpose. A skill is added after the model has demonstrably got
something wrong, never in anticipation. Candidates are proposed at milestone boundaries and
sit on the board as drafts until the evidence exists. `docs/skills.md` has the process and
the gate.

## Layout

```
skills/<name>/SKILL.md          the skill
evals/<name>-<case>/prompt.md   one eval case: frontmatter and the prompt
evals/<name>-<case>/graders/    one grader per file: regex, tool_used, file_exists, llm
evals/results/                  written by `claude plugin eval`; ignored by git
```

## Running

```sh
claude plugin validate --strict .claude/plugins/cmd-dev
claude plugin eval .claude/plugins/cmd-dev --trust-plugin --threshold 1.0 --no-publish
```

The eval runs real agent sessions on your credential. `--ablation with-without` (the default
when the plugin resolves) also runs each case without the plugin and reports the delta, which
is the number that says whether the skill earns its place.
